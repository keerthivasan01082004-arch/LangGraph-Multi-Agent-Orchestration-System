"""Tool registry: declares the catalog and exposes selection helpers.

The Executor agent picks tools described in the registry; the registry also
enforces policy (approval-gated tools, disabled tools).
"""

from __future__ import annotations

from app.tools.base import Tool
from app.tools import definitions as d

WEB_SEARCH = Tool(
    name="web_search",
    description="Search the public web for recent information. Use for current events or external facts.",
    parameters={"query": {"type": "string", "description": "Search query"}, "limit": {"type": "integer", "minimum": 1, "maximum": 10}},
    func=d.web_search,
)

CALCULATOR = Tool(
    name="calculator",
    description="Evaluate a simple arithmetic expression like '8 * (2.5 + 1)'.",
    parameters={"expr": {"type": "string", "description": "Arithmetic expression to evaluate"}},
    func=d.calculate,
)

RETRIEVAL = Tool(
    name="retrieve_documents",
    description="Search the workspace knowledge base (FAQ, manuals, SOPs). Use for grounded answer material.",
    parameters={
        "query": {"type": "string", "description": "Search query"},
        "workspace_id": {"type": "string", "description": "Workspace identifier"},
    },
    func=d.retrieve_documents,
)

WEATHER = Tool(
    name="get_weather",
    description="Current weather for a city (Open-Meteo).",
    parameters={"city": {"type": "string"}},
    func=d.get_weather,
)

TICKERS = Tool(
    name="get_tickers",
    description="Current price and summary for a ticker symbol (yfinance).",
    parameters={"symbol": {"type": "string"}},
    func=d.get_tickers,
)

RUN_SQL = Tool(
    name="run_sql_query",
    description="Run a read-only SQL query against the workspace database.",
    parameters={"query": {"type": "string"}},
    func=d.run_sql_query,
    read_only=True,
)

EMAIL_DRAFT = Tool(
    name="draft_email",
    description="Draft an email (no sending).",
    parameters={
        "recipient": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    func=d.draft_email,
    read_only=True,
)

EMAIL_SEND = Tool(
    name="send_email",
    description="Send a drafted email. REQUIRES HUMAN APPROVAL.",
    parameters={
        "recipient": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    func=d.send_email,
    needs_approval=True,
    read_only=False,
)

PYTHON_EXEC = Tool(
    name="run_python",
    description="Execute a small Python snippet in a sandbox. DISABLED by default.",
    parameters={"code": {"type": "string"}},
    func=d.run_python,
    needs_approval=True,
    read_only=False,
)

ALL_TOOLS: dict[str, Tool] = {t.name: t for t in (WEB_SEARCH, CALCULATOR, RETRIEVAL, WEATHER, TICKERS, RUN_SQL, EMAIL_DRAFT, EMAIL_SEND, PYTHON_EXEC)}

# Subsets the Executor offers by default (approval-gated tools added per task).
SAFE_TOOLS: list[Tool] = [WEB_SEARCH, CALCULATOR, RETRIEVAL, WEATHER, TICKERS, EMAIL_DRAFT]


def get_tool(name: str) -> Tool:
    if name not in ALL_TOOLS:
        raise KeyError(f"unknown tool: {name}")
    return ALL_TOOLS[name]


def openai_schemas(names: list[str] | None = None) -> list[dict[str, object]]:
    selected = [ALL_TOOLS[n] for n in names] if names else SAFE_TOOLS
    return [t.openai_schema() for t in selected]