# AGENTS.md

Guidance for AI coding agents working in this repository.

## Project

Multi-agent AI orchestration platform ("Conductor") built with LangGraph.
Four specialized agents (Planner, Researcher, Tool Executor, Critic) orchestrated
as a state machine, backed by a fine-tuned Mistral-7B (LoRA/QLoRA, 4-bit) served
via vLLM, exposed through FastAPI and fronted by Next.js.

## Repo layout (top level)

- `backend/` — FastAPI service, LangGraph graph, agents, tools, memory, ingestion
- `frontend/` — Next.js (App Router, TS, Tailwind)
- `finetune/` — dataset build + LoRA/QLoRA training + eval + export scripts
- `infra/` — Terraform, Kubernetes manifests, Docker, monitoring
- `.github/workflows/` — CI/CD
- `docs/` — full system design documentation (20 sections)

## Conventions

- Python: `uv` + `pyproject.toml`. Target 3.11+. Use Pydantic v2 schemas everywhere.
- Typing: strict; every agent/tool exposes typed Input/Output.
- APIs: FastAPI, versioned under `/api/v1/`, OpenAPI auto-generated, JWT auth.
- DB: SQLAlchemy 2.0 + Alembic against PostgreSQL. Vector store: Qdrant.
- LangGraph nodes are plain functions on a shared `AgentState`; edges are explicit.
- No secrets in code: everything from env / `backend/.env.example`.

## Commands

- Backend deps: `uv sync` (in `backend/`)
- Lint: `ruff check backend`
- Type check: `mypy backend`
- Test: `pytest backend/tests`
- Run API (dev): `uvicorn app.main:app --reload`

## Rules

- Never commit model weights, `.env`, or real API keys (see `.gitignore`).
- Keep CI green: `ruff`, `mypy`, `pytest` must pass for new code.
- Docs mirror the implementation — update `docs/` when architecture changes.