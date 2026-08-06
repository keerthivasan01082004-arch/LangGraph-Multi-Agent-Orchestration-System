"""Agent metadata: purpose, input contract, output, tools, handoff conditions.

The actual node implementations live in app/agents/nodes.py; this module is the
declarative spec used by the graph builder and the docs/06-agent-design.md
table so the two always stay in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.tools.registry import ALL_TOOLS


@dataclass(frozen=True)
class AgentSpec:
    name: str
    purpose: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    tools: tuple[str, ...] = ()
    memory: str = "none"
    fallback: str = "researcher"  # agent route to retry on failure
    handoff_on: str = "plan complete"

    def openai_tool_schemas(self) -> list[dict[str, object]]:
        return [ALL_TOOLS[t].openai_schema() for t in self.tools if t in ALL_TOOLS]


AGENTS: dict[str, AgentSpec] = {
    "planner": AgentSpec(
        name="planner",
        purpose="Decompose the request into an ordered task list and a capability plan.",
        inputs=("input",),
        outputs=("plan", "tasks", "needs_retrieval", "needs_web", "needs_tools"),
        handoff_on="task list ready",
    ),
    "researcher": AgentSpec(
        name="researcher",
        purpose="Gather grounded evidence from the workspace knowledge base and web.",
        inputs=("input", "plan", "tasks"),
        outputs=("retrieved", "research_notes", "citations"),
        tools=("retrieve_documents", "web_search"),
        handoff_on="evidence collected with confidence",
    ),
    "executor": AgentSpec(
        name="executor",
        purpose="Execute tool calls to satisfy tasks requiring live data or side effects.",
        inputs=("tasks", "input"),
        outputs=("tool_results",),
        tools=("calculator", "get_weather", "get_tickers", "run_sql_query", "draft_email", "send_email", "run_python"),
        handoff_on="tools exhausted or NO_TOOL",
    ),
    "critic": AgentSpec(
        name="critic",
        purpose="Score the draft answer; approve, or reject to trigger a revision loop.",
        inputs=("input", "answer", "research_notes"),
        outputs=("critique", "confidence", "iterations"),
        handoff_on="score >= 0.7 or max iterations",
    ),
}