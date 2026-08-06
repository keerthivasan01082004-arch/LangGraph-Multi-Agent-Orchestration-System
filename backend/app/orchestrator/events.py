"""SSE event envelope for the streaming chat endpoint.

Events emitted to the browser (docs/04-user-interaction-flow.md):
  role:    {"type": "assistant.start"}
  agent:   {"type": "agent.started", "agent": "planner"}    (node boundaries)
  token:   {"type": "token", "delta": "..."}                 (token streaming)
  done:    {"type": "done", "answer": "...", "confidence": 0.0}
  usage:   {"type": "usage", "model": "...", "cost_usd": 0.0, "tokens": n}
  error:   {"type": "error", "message": "..."}
"""

from __future__ import annotations

from typing import Any


def agent_started(agent: str) -> dict[str, Any]:
    return {"type": "agent.started", "agent": agent}


def token(delta: str) -> dict[str, Any]:
    return {"type": "token", "delta": delta}


def usage(model: str, cost_usd: float, tokens: int) -> dict[str, Any]:
    return {"type": "usage", "model": model, "cost_usd": cost_usd, "tokens": tokens}


def done(answer: str, confidence: float, citations: list[str] | None = None) -> dict[str, Any]:
    return {"type": "done", "answer": answer, "confidence": confidence, "citations": citations or []}


def error(message: str) -> dict[str, Any]:
    return {"type": "error", "message": message}


def assistant_start() -> dict[str, Any]:
    return {"type": "assistant.start"}