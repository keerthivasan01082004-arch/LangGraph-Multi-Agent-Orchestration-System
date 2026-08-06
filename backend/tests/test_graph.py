"""Tests for the LangGraph builder: topology, routing, critique loop."""

from app.graph.builder import (
    MAX_ITERATIONS,
    _route_after_critic,
    _route_after_planner,
    _route_after_researcher,
    build_graph,
)


def test_graph_builds_with_expected_nodes():
    graph = build_graph()
    assert {"planner", "researcher", "executor", "critic", "finalizer"} <= set(graph.nodes)


def test_planner_routes_to_tools_when_needed():
    assert _route_after_planner({"needs_tools": True, "needs_retrieval": True}) == "executor"


def test_planner_routes_to_researcher_when_only_research():
    assert _route_after_planner({"needs_tools": False, "needs_retrieval": True, "needs_web": True}) == "researcher"


def test_planner_routes_to_finalizer_for_direct_answers():
    assert _route_after_planner({"needs_tools": False, "needs_retrieval": False, "needs_web": False}) == "finalizer"


def test_researcher_skips_executor_when_no_tools():
    assert _route_after_researcher({"needs_tools": False}) == "finalizer"
    assert _route_after_researcher({"needs_tools": True}) == "executor"


def test_critic_loop_terminates_within_budget():
    # Low confidence, iteration budget not exhausted → loop back to researcher.
    assert _route_after_critic({"confidence": 0.4, "iterations": 1}) == "researcher"
    # Budget exhausted → accept best effort.
    assert _route_after_critic({"confidence": 0.4, "iterations": MAX_ITERATIONS}) == "END"
    # High confidence → END.
    assert _route_after_critic({"confidence": 0.85, "iterations": 1}) == "END"