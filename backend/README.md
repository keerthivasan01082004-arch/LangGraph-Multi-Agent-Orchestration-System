# Conductor Backend

FastAPI service that hosts the LangGraph multi-agent orchestration graph.

- **API**: versioned under `/api/v1` (auth, documents, conversations/SSE, usage, health)
- **Agents**: Planner, Researcher, Tool Executor, Critic (`app/agents/`)
- **Graph**: typed `AgentState` state machine with conditional routing and checkpointing (`app/graph/`)
- **Streaming**: LangGraph `astream_events` bridged to SSE (`app/orchestrator/`)
- **Models**: OpenAI-compatible vLLM gateway with LiteLLM fallback and per-token cost accounting (`app/models/`)
- **Storage**: PostgreSQL (SQLAlchemy 2.0 + Alembic), Qdrant vectors, Redis sessions
- **Ingestion**: Celery pipeline with text parsers and token-aware chunking (`app/ingestion/`)

## Development

```bash
uv sync --extra dev
cp .env.example .env        # fill in secrets
uvicorn app.main:app --reload --port 8000
```

## Checks

```bash
uv run ruff check app
uv run mypy app
uv run pytest tests
```

## Docs

Full system design: `docs/10-rest-api.md`, `docs/11-database.md`,
`docs/05-langgraph-system.md`, `docs/06-agent-design.md`.