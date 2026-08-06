"""LangGraph graph construction.

Topology:
  START → planner → route
     route ──(tools)─────────────▶ executor ─┐
     route ──(research)─────────▶ researcher ─┴──▶ finalizer → critic
     route ──(answer directly)────────────────┘      │ approve ▶ END
                                                     └ reject (≤3) ▶ researcher

Conditional routing, a finite critique loop, and an interrupt-based
human-in-the-loop approval path for sensitive tools. See docs/05-langgraph-system.md.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.agents.nodes import critic_node, executor_node, finalizer_node, planner_node, researcher_node
from app.graph.state import AgentState

MAX_ITERATIONS = 3
CRITIC_APPROVAL_SCORE = 0.7


def _route_after_planner(state: AgentState) -> str:
    if state.get("needs_tools"):
        return "executor"
    if state.get("needs_retrieval") or state.get("needs_web"):
        return "researcher"
    return "finalizer"


def _route_after_researcher(state: AgentState) -> str:
    return "executor" if state.get("needs_tools") else "finalizer"


def _route_after_critic(state: AgentState) -> str:
    if state.get("confidence", 0.0) >= CRITIC_APPROVAL_SCORE:
        return "END"
    if state.get("iterations", 0) >= MAX_ITERATIONS:
        return "END"  # budget exhausted — ship best effort
    return "researcher"  # loop back with accumulated critique


def build_graph(checkpointer: Any = None, store: Any = None):
    """Build and compile the graph. `checkpointer` enables threads/resume,
    `store` enables long-term memory."""
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("executor", executor_node)
    graph.add_node("critic", critic_node)
    graph.add_node("finalizer", finalizer_node)

    graph.add_edge(START, "planner")
    graph.add_conditional_edges(
        "planner",
        _route_after_planner,
        {"executor": "executor", "researcher": "researcher", "finalizer": "finalizer"},
    )
    graph.add_conditional_edges("researcher", _route_after_researcher, {"executor": "executor", "finalizer": "finalizer"})
    graph.add_edge("executor", "finalizer")
    graph.add_edge("finalizer", "critic")
    graph.add_conditional_edges("critic", _route_after_critic, {"researcher": "researcher", "END": END})

    return graph.compile(checkpointer=checkpointer, store=store)