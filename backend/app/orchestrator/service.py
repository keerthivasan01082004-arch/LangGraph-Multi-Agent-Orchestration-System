"""Streaming bridge: LangGraph -> SSE for the chat API.

Consumes graph.astream(stream_mode=["values", "custom"]):
  - "values" : full post-node state; emits agent.started for each node
  - "custom" : token events written by the streaming finalizer

After the run it persists the assistant message and writes UsageRecord rows
for cost analytics (docs/10-rest-api.md, docs/14-monitoring.md).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.db.models import Message, MessageRole, UsageRecord
from app.graph.builder import stream_graph
from app.orchestrator import events as ev

_NODE_TO_AGENT = {
    "planner": "planner",
    "researcher": "researcher",
    "executor": "executor",
    "draft": "draft",
    "critic": "critic",
    "finalizer": "finalizer",
}


async def run_conversation_stream(
    thread_id: str,
    user_message: dict[str, object],
    workspace_id: object,
    conversation_id: object,
    user_id: object,
) -> AsyncIterator[dict[str, object]]:
    inputs = {
        "input": user_message["content"],
        "workspace_id": str(workspace_id),
        "messages": [user_message],
        "iterations": 0,
    }

    final_answer = ""
    usage_rows: list[UsageRecord] = []
    confidence = 1.0

    yield ev.assistant_start()
    async for mode, payload in await stream_graph(inputs, thread_id):
        if mode == "custom":
            if payload.get("type") == "token":
                final_answer += payload.get("delta", "")
            yield payload
            continue
        if mode == "values":
            node = _NODE_TO_AGENT.get(payload.get("current_agent", ""), "")
            if node:
                yield ev.agent_started(node)
            if payload.get("answer"):
                confidence = float(payload.get("confidence", 1.0))
                yield ev.done(payload["answer"], confidence, payload.get("citations", []))
            for u in payload.get("usage", []):
                usage_rows.append(
                    UsageRecord(
                        workspace_id=workspace_id,
                        user_id=user_id,
                        conversation_id=conversation_id,
                        model_id=u.get("model", "unknown"),
                        agent=u.get("agent", "unknown"),
                        prompt_tokens=int(u.get("input_tokens", 0)),
                        completion_tokens=int(u.get("output_tokens", 0)),
                        total_tokens=int(u.get("input_tokens", 0)) + int(u.get("output_tokens", 0)),
                        cost_usd=float(u.get("cost_usd", 0.0)),
                        cached=False,
                    )
                )

    if final_answer:
        _persist_assistant_message(conversation_id, final_answer, thread_id, workspace_id, usage_rows, user_id)


def _persist_assistant_message(
    conversation_id: str,
    answer: str,
    thread_id: str,
    workspace_id: str,
    usage_rows: list[UsageRecord],
    user_id: str,
) -> None:
    """Write the assistant message and usage records after streaming completes."""
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        db.add(
            Message(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT,
                content=answer,
                metadata_={"thread_id": thread_id, "streamed": True},
            )
        )
        for row in usage_rows:
            row.workspace_id = workspace_id
            row.user_id = user_id
            db.add(row)
        db.commit()