"""Shared AgentState schema for the Conductor graph.

Channels annotated with operator.add accumulate (append) across nodes; scalar
channels are overwritten by the latest node. Full design rationale in
docs/05-langgraph-system.md.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class ResearchNote(TypedDict):
    id: str
    claim: str
    evidence: str
    source: str
    score: float


class ToolResult(TypedDict):
    tool: str
    args: dict[str, Any]
    result: str
    status: str  # "ok" | "error"


class ContextChunk(TypedDict):
    text: str
    score: float
    document_id: str


class AgentState(TypedDict, total=False):
    # The original user request.
    input: str

    # Tenant scope for retrieval isolation.
    workspace_id: str

    # Chat history handled via LangGraph thread checkpoint.
    messages: Annotated[list[dict[str, Any]], operator.add]

    # Planner output.
    plan: str
    tasks: Annotated[list[dict[str, Any]], operator.add]
    current_agent: str

    # Planner capability flags drive conditional routing.
    needs_retrieval: bool
    needs_web: bool
    needs_tools: bool

    # Accumulated evidence and tool outputs.
    research_notes: Annotated[list[ResearchNote], operator.add]
    retrieved: Annotated[list[ContextChunk], operator.add]
    tool_results: Annotated[list[ToolResult], operator.add]

    # Traceability (rendered as citations in the final answer).
    citations: Annotated[list[str], operator.add]

    # Critic loop control.
    critique: str
    confidence: float
    iterations: int

    # Language model consumption for cost accounting.
    usage: Annotated[list[dict[str, Any]], operator.add]

    # Final answer (written once by the finalizer).
    answer: str

    # Human-in-the-loop.
    pending_approval: str
    approval_decision: str  # granted | rejected
    resume_action: dict[str, Any] | None