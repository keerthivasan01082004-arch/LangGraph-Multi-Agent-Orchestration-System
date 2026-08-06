"""LangGraph graph assembly.

Pipeline:
    START -> planner -> (researcher -> executor?) -> draft -> critic -> finalize -> END

Conditional edges:
    planner  -> researcher | executor | draft   (capability flags)
    researcher -> executor | draft              (tools required?)
    critic   -> draft (reject, revise) | finalize (approve)

Parallelism: the researcher node fans out per-task with the Send API in
production (see docs/05-langgraph-system.md); the scaffold keeps a single
pass for determinism and cost.

Human-in-the-loop: approval-gated tools interrupt inside executor_node; the
caller resumes with Command(resume="granted") via the checkpointer.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import (
    critic_node,
    executor_node,
    finalizer_node,
    planner_node,
    researcher_node,
    streaming_finalize_node,
)
from app.config import get_settings
from app.graph.checkpointer import get_graph_checkpointer, get_store
from app.graph.routes import route_after_critic, route_after_planner, route_after_research
from app.graph.state import AgentState

_GRAPH = None


def build_graph(enable_critic: bool | None = None) -> Any:
    """Build and compile the Conductor graph with Postgres checkpointing."""
    global _GRAPH
    settings = get_settings()
    if enable_critic is None:
        enable_critic = settings.enable_critic

    g = StateGraph(AgentState)
    g.add_node("planner", planner_node)
    g.add_node("researcher", researcher_node)
    g.add_node("executor", executor_node)
    g.add_node("draft", finalizer_node)
    g.add_node("critic", critic_node)
    g.add_node("finalize", streaming_finalize_node)

    g.add_edge(START, "planner")
    g.add_conditional_edges(
        "planner",
        route_after_planner,
        {"researcher": "researcher", "executor": "executor", "draft": "draft"},
    )
    g.add_conditional_edges("researcher", route_after_research, {"executor": "executor", "draft": "draft"})
    g.add_edge("executor", "draft")

    if enable_critic:
        g.add_edge("draft", "critic")
        g.add_conditional_edges("critic", route_after_critic, {"draft": "draft", "finalize": "finalize"})
    else:
        g.add_edge("draft", "finalize")

    g.add_edge("finalize", END)

    graph = g.compile(checkpointer=get_graph_checkpointer(), store=get_store())
    if _GRAPH is None:
        _GRAPH = graph
    return graph


def get_graph() -> Any:
    if _GRAPH is None:
        return build_graph()
    return _GRAPH


def run_graph(inputs: dict[str, Any], thread_id: str, *, resume: Any | None = None) -> dict[str, Any]:
    """Synchronous run (used by Celery batches and tests)."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    if resume is not None:
        from langgraph.types import Command

        inputs = Command(resume=resume)
    return graph.invoke(inputs, config=config)


async def stream_graph(inputs: dict[str, Any], thread_id: str) -> Any:
    """Stream the graph: yields ('custom', event) token events and
    ('values', state) after each node for the SSE bridge."""
    graph = get_graph()
    config = {"configurable": {"thread_id": thread_id}}
    return graph.astream(inputs, config=config, stream_mode=["values", "custom"])