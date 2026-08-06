"""Streaming bridge between the FastAPI SSE endpoint and the compiled graph.

run_conversation_stream(thread_id, user_message, workspace_id):
  1. inject the user message into AgentState
  2. stream graph events (astream_events v2) and translate them to SSE events
  3. emit the terminal answer + evidence, then persist assistant message + usage

Human-in-the-loop: sensitive tool calls raise an interrupt; the generator
emits a `human_approval` event and the API layer can resume the same thread
via a separate endpoint. See docs/10-rest-api.md and docs/20-code-flow.md.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import structlog

from app.graph.builder import build_graph
from app.graph.checkpointer import get_checkpointer, get_store
from app.graph.event import (
    agent_end,
    agent_start,
    answer_event,
    done,
    error,
    evidence,
    tool_call_event,
    tool_result,
    token,
)

logger = structlog.get_logger("orchestrator")

_graph_cache: Any = None
_NODES = {"planner", "researcher", "executor", "critic", "finalizer"}


def get_graph():
    global _graph_cache
    if _graph_cache is None:
        _graph_cache = build_graph(checkpointer=get_checkpointer(), store=get_store())
    return _graph_cache


def build_config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


async def run_conversation_stream(
    thread_id: str,
    user_message: dict[str, Any],
    workspace_id: str,
) -> AsyncIterator[dict[str, Any]]:
    graph = get_graph()
    config = build_config(thread_id)

    initial: dict[str, Any] = {
        "input": user_message.get("content", ""),
        "workspace_id": str(workspace_id),
        "messages": [{"role": "user", "content": user_message.get("content", "")}],
    }

    final_state: dict[str, Any] = {}
    try:
        async for event in graph.astream_events(initial, config=config, version="v2"):
            kind = event.get("event", "")
            data = event.get("data", {})
            node = (event.get("metadata") or {}).get("langgraph_node", "")

            if kind == "on_chain_start" and node in _NODES:
                yield agent_start(node)

            elif kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                delta = getattr(chunk, "content", None)
                if delta:
                    yield token(node, delta)

            elif kind == "on_tool_start":
                yield tool_call_event(data.get("name", "tool"), data.get("input") or {})

            elif kind == "on_tool_end":
                output = data.get("output", "")
                yield tool_result(data.get("name", "tool"), "ok", str(output))

            elif kind == "on_chain_end" and node in _NODES:
                yield agent_end(node)
                outputs = data.get("output")
                if isinstance(outputs, dict):
                    final_state.update(outputs)

            elif kind == "on_interrupt":
                yield {"event": "human_approval", "question": data.get("value", {})}
    except Exception as exc:
        logger.exception("graph_stream_error")
        yield error(f"agent pipeline failed: {exc}")
        return

    if final_state.get("research_notes"):
        yield evidence(final_state["research_notes"])
    if final_state.get("answer"):
        yield answer_event(
            final_state["answer"],
            [str(c) for c in final_state.get("citations", [])],
            float(final_state.get("confidence", 0.0)),
        )
    _persist_results(thread_id, final_state)
    logger.info("stream_complete", thread=thread_id, tokens=sum(u.get("total_tokens", 0) for u in final_state.get("usage", [])))
    yield done()


def _persist_results(thread_id: str, final_state: dict[str, Any]) -> None:
    """Best-effort persistence of the assistant message + usage rows."""
    if not final_state:
        return
    try:
        from sqlalchemy import select

        from app.db.models import Conversation, Message, MessageRole
        from app.db.session import SessionLocal
        from app.models.cost import persist_usage

        with SessionLocal() as db:
            conv = db.execute(select(Conversation).where(Conversation.thread_id == thread_id)).scalar_one_or_none()
            if conv is None:
                return
            if final_state.get("answer"):
                db.add(
                    Message(
                        conversation_id=conv.id,
                        role=MessageRole.ASSISTANT,
                        content=final_state["answer"],
                        metadata_={"tokens": sum(u.get("total_tokens", 0) for u in final_state.get("usage", []))},
                    )
                )
                db.commit()
            for usage in final_state.get("usage", []):
                persist_usage(db, conv, usage)
    except Exception:
        logger.exception("persist_failed", thread=thread_id)