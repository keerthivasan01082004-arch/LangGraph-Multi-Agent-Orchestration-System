"""Conditional routing predicates for the Conductor graph.

Each function inspects the accumulated AgentState and returns the next node
name (or END). Design rationale in docs/05-langgraph-system.md.
"""

from __future__ import annotations

from typing import Any

MAX_ITERATIONS = 2


def route_after_planner(state: dict[str, Any]) -> str:
    if state.get("needs_retrieval") or state.get("needs_web"):
        return "researcher"
    if state.get("needs_tools"):
        return "executor"
    return "draft"


def route_after_research(state: dict[str, Any]) -> str:
    if state.get("needs_tools"):
        return "executor"
    return "draft"


def route_after_critic(state: dict[str, Any]) -> str:
    if state.get("current_agent") == "critic" and state.get("confidence", 0.0) < 0.7:
        return "draft"
    return "finalize"


def should_approve(state: dict[str, Any]) -> str:
    """Gate: if a pending approval exists, route to the approval checkpoint."""
    return "approve" if state.get("pending_approval") else "draft"