"""Four specialized agents orchestrated by the LangGraph state machine.

Each agent is a plain function `(state) -> partial state update`. Full agent
specs (prompts, failure handling, confidence, handoff conditions) in
docs/06-agent-design.md.
"""

from __future__ import annotations

import json
from typing import Any

from app.models.gateway import chat_with_fallback
from app.tools.registry import SAFE_TOOLS, ALL_TOOLS

SYSTEM_PROMPTS: dict[str, str] = {
    "planner": (
        "You are the Planner agent of a research system. Decompose the user's request into a "
        "concise, ordered task list. Decide which capabilities are needed: RETRIEVAL (search the "
        "user's documents), WEB (live web research), TOOLS (side effects like emails), NONE "
        "(answer directly). Respond as strict JSON with keys: "
        '{"tasks": [...], "needs_retrieval": bool, "needs_web": bool, "needs_tools": bool, "strategy": "..."}.'
    ),
    "researcher": (
        "You are the researcher. Using the provided retrieved evidence and your own knowledge, "
        "produce up to five factual claims relevant to the plan. For each claim return JSON: "
        '{"claim": "...", "evidence": "...", "source": "doc:<id>" or "web", "confidence": 0.0-1.0}. '
        "Do not invent facts; if evidence is weak, lower confidence."
    ),
    "executor": (
        "You are the tool executor. Choose and call tools to satisfy the current task. If a tool "
        "result is sufficient, summarize it. If no tool is needed, say 'NO_TOOL'. Prefer read-only tools."
    ),
    "critic": (
        "You are the critic. Evaluate the draft answer against the research brief and evidence. "
        'Return JSON: {"score": 0.0-1.0, "issues": [...], "revised_answer": "..." or null}. '
        "Score below 0.7 is a rejection; the system will iterate."
    ),
    "finalizer": (
        "You are the writer. Produce the final answer grounded in the evidence and citations, "
        "concise, with numbered citations in brackets referencing the evidence list."
    ),
}


def planner_node(state: dict[str, Any]) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPTS["planner"]},
        {"role": "user", "content": state["input"]},
    ]
    completion = chat_with_fallback(messages, agent="planner")
    try:
        parsed = json.loads(completion.content or "{}")
    except json.JSONDecodeError:
        parsed = {"tasks": [state["input"]], "needs_retrieval": True, "needs_web": False, "needs_tools": False, "strategy": ""}
    return {
        "plan": parsed.get("strategy", ""),
        "tasks": parsed.get("tasks", []),
        "needs_retrieval": parsed.get("needs_retrieval", True),
        "needs_web": parsed.get("needs_web", False),
        "needs_tools": parsed.get("needs_tools", False),
        "current_agent": "planner",
        "usage": _usage(completion, "planner"),
    }


def researcher_node(state: dict[str, Any]) -> dict[str, Any]:
    from app.services import embeddings, vectorstore

    retrieved: list[dict[str, object]] = []
    workspace_id = state.get("workspace_id")
    if workspace_id:
        vector = embeddings.embed_query(state["input"])
        retrieved = vectorstore.search(workspace_id, vector, limit=6)

    prompt = [
        {"role": "system", "content": SYSTEM_PROMPTS["researcher"]},
        {"role": "user", "content": f"Question: {state['input']}\n\nEvidence:\n{json.dumps(retrieved[:3], default=str)}"},
    ]
    completion = chat_with_fallback(prompt, agent="researcher")
    try:
        notes = json.loads(completion.content or "[]")
        if isinstance(notes, dict):
            notes = [notes]
    except json.JSONDecodeError:
        notes = []

    context = [
        {"text": str(r.get("text", "")), "score": float(r.get("score", 0.0)), "document_id": str(r.get("document_id", ""))}
        for r in retrieved
    ]
    return {
        "retrieved": context,
        "research_notes": notes,
        "citations": _citations_from(retrieved),
        "current_agent": "researcher",
        "usage": _usage(completion, "researcher"),
    }


def executor_node(state: dict[str, Any]) -> dict[str, Any]:
    from langgraph.types import interrupt

    from app.tools.registry import ALL_TOOLS, SAFE_TOOLS

    prompt = [
        {"role": "system", "content": SYSTEM_PROMPTS["executor"]},
        {"role": "user", "content": f"Request: {state.get('input')}\nTask checklist: {json.dumps(state.get('tasks', []))}"},
        *state.get("messages", []),
    ]
    completion = chat_with_fallback(prompt, tools=openai_schemas_of(SAFE_TOOLS), agent="executor")

    results: list[dict[str, Any]] = list(state.get("tool_results", []))
    for call in completion.tool_calls:
        name = call.get("name", "")
        args = json.loads(call.get("arguments", "{}")) if isinstance(call.get("arguments", ""), str) else call.get("arguments", {})
        tool = ALL_TOOLS.get(name)
        if tool is None:
            continue
        if tool.needs_approval:
            # Human-in-the-loop: pause the graph until a decision is supplied.
            decision = interrupt({"question": f"Approve execution of {name}?", "tool": name, "args": args})
            if decision != "granted":
                results.append({"tool": name, "args": args, "result": "rejected by user", "status": "rejected"})
                continue
        try:
            results.append({"tool": name, "args": args, "result": tool.run(args), "status": "ok"})
        except Exception as exc:  # tool-level failure → record, do not crash the graph
            results.append({"tool": name, "args": args, "result": str(exc), "status": "error"})
    return {"tool_results": results, "current_agent": "executor", "usage": _usage(completion, "executor")}


def critic_node(state: dict[str, Any]) -> dict[str, Any]:
    prompt = [
        {"role": "system", "content": SYSTEM_PROMPTS["critic"]},
        {
            "role": "user",
            "content": json.dumps(
                {
                    "request": state.get("input"),
                    "draft": state.get("answer", ""),
                    "notes": state.get("research_notes", []),
                }
            ),
        },
    ]
    completion = chat_with_fallback(prompt, agent="critic")
    try:
        verdict = json.loads(completion.content or "{}")
    except json.JSONDecodeError:
        verdict = {"score": 0.5, "issues": ["critic returned malformed JSON"]}
    return {
        "critique": str(verdict.get("issues", "no issues listed")),
        "confidence": float(verdict.get("score", 0.5)),
        "iterations": int(state.get("iterations", 0)) + 1,
        "current_agent": "critic",
        "usage": _usage(completion, "critic"),
    }


def finalizer_node(state: dict[str, Any]) -> dict[str, Any]:
    citations = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(state.get("citations", [])))
    prompt = [
        {"role": "system", "content": SYSTEM_PROMPTS["finalizer"]},
        {
            "role": "user",
            "content": (
                f"Question: {state.get('input')}\n"
                f"Evidence: {json.dumps(state.get('research_notes', []))}\n"
                f"Citations:\n{citations}"
            ),
        },
    ]
    completion = chat_with_fallback(prompt, agent="finalizer")
    return {"answer": completion.content, "current_agent": "finalizer", "usage": _usage(completion, "finalizer")}


async def streaming_finalize_node(state: dict[str, Any]) -> dict[str, Any]:
    """Final answer generation streamed to the client via the custom stream writer.

    Tokens are pushed as {"type": "token", "delta": "..."} custom stream events,
    which the SSE bridge (app/orchestrator/service.py) forwards to the browser.
    """
    import tiktoken

    from langgraph.config import get_stream_writer

    from app.models.gateway import LLMUnavailableError, stream_complete

    writer = get_stream_writer()
    citations = "\n".join(f"[{i + 1}] {c}" for i, c in enumerate(state.get("citations", [])))
    prompt = [
        {"role": "system", "content": SYSTEM_PROMPTS["finalizer"]},
        {
            "role": "user",
            "content": (
                f"Question: {state.get('input')}\n"
                f"Evidence: {json.dumps(state.get('research_notes', []))}\n"
                f"Citations:\n{citations}"
            ),
        },
    ]

    parts: list[str] = []
    completion = None
    try:
        async for delta, final in stream_complete(prompt, agent="finalizer"):
            if delta:
                parts.append(delta)
                writer({"type": "token", "delta": delta})
            elif final is not None:
                completion = final
    except LLMUnavailableError:
        writer({"type": "error", "message": "model unavailable"})
        return {"current_agent": "finalizer"}

    if completion is None:
        enc = tiktoken.get_encoding("cl100k_base")
        completion = completion or _fallback_completion(prompt, parts, enc)

    return {
        "answer": "".join(parts) or state.get("answer", ""),
        "current_agent": "finalizer",
        "usage": _usage(completion, "finalizer"),
    }


def _fallback_completion(messages: list[dict[str, str]], parts: list[str], enc) -> Any:
    from app.models.gateway import Completion, _estimate_cost

    text = "".join(parts)
    input_tokens = sum(len(enc.encode(m["content"])) for m in messages)
    output_tokens = len(enc.encode(text))
    return Completion(
        content=text,
        model="(estimated)",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=_estimate_cost("conductor/mistral-7b", input_tokens, output_tokens),
    )


def _usage(completion: Any, agent: str) -> list[dict[str, Any]]:
    return [
        {
            "agent": agent,
            "model": completion.model,
            "input_tokens": completion.input_tokens,
            "output_tokens": completion.output_tokens,
            "cost_usd": completion.cost_usd,
        }
    ]


def _citations_from(retrieved: list[dict[str, object]]) -> list[str]:
    return [f"doc:{r.get('document_id', '?')}" for r in retrieved[:6]]


def openai_schemas_of(tools: list[Any]) -> list[dict[str, object]]:
    return [t.openai_schema() for t in tools]