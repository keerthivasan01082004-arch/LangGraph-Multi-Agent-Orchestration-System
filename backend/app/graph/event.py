"""Streaming event payloads bridging the graph to the SSE channel.

Event names consumed by the frontend (docs/10-rest-api.md):
  plan, agent_start, agent_end, token, tool_call, tool_result,
  memory, answer, error, done
"""

from __future__ import annotations

from typing import Any


def build_event(kind: str, **payload: Any) -> dict[str, Any]:
    return {"event": kind, **payload}


def agent_start(agent: str, task: str = "") -> dict[str, Any]:
    return build_event("agent_start", agent=agent, task=task)


def agent_end(agent: str) -> dict[str, Any]:
    return build_event("agent_end", agent=agent)


def token(agent: str, delta: str) -> dict[str, Any]:
    return build_event("token", agent=agent, delta=delta)


def tool_call_event(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return build_event("tool_call", tool=tool, args=args)


def tool_result(tool: str, status: str, summary: str) -> dict[str, Any]:
    return build_event("tool_result", tool=tool, status=status, summary=summary[:500])


def evidence(notes: list[dict[str, Any]]) -> dict[str, Any]:
    return build_event("evidence", notes=notes)


def answer_event(answer: str, citations: list[str], confidence: float) -> dict[str, Any]:
    return build_event("answer", answer=answer, citations=citations, confidence=round(confidence, 3))


def error(message: str) -> dict[str, Any]:
    return build_event("error", message=message)


def done() -> dict[str, Any]:
    return build_event("done")