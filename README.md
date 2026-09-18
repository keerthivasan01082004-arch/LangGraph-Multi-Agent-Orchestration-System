# Conductor — LangGraph Multi-Agent Orchestration System

A production-grade, enterprise multi-agent AI orchestration platform. Four
specialized agents — **Planner**, **Researcher**, **Tool Executor**, and **Critic** —
are orchestrated as an explicit LangGraph state machine to answer complex,
deep-research questions against your own documents and live tools, with
citations, confidence scoring, streaming, cost accounting, and human-in-the-loop
approval for sensitive actions.

The system is backed by a domain fine-tuned **Mistral-7B** (LoRA/QLoRA, 4-bit
quantization) served efficiently via **vLLM**, exposed through a versioned
**FastAPI** REST API, and fronted by a **Next.js** streaming chat UI. A LiteLLM
shim provides a frontier-model fallback when the fine-tuned model's confidence
is low.

---

## Why this exists

Single-shot LLM chat can't reliably do research that requires planning, live
tools, and critique. "Conductor" decomposes a request into a plan, executes
research and tool calls, and runs a critic pass before answering — modeled as
an explicit state machine so every step is observable, reproducible
(checkpointed), and auditable.

Key differentiators:

- **Plan → Act → Verify feedback loop**: planning is not a one-shot prompt; the
  graph conditionally re-loops the critic over the research before finalizing.
- **Tool use with safety gates**: tool calls are JSON-schema validated and gated
  behind approval hooks for sensitive operations.
- **Cost transparency**: every agent step reports token usage and estimated USD
  cost; per-conversation usage summaries are exposed through the API.
- **Own your model**: a Mistral-7B fine-tuned for this domain cuts inference
  cost roughly 40% vs. a pretrained chat baseline at equal output quality
  (see `docs/09-fine-tuning.md` and `docs/16-cost-optimization.md`).

## Architecture at a glance

```
React/Next.js (streaming chat)  →  FastAPI gateway (JWT, /api/v1)
                                          │
                          ┌───────────────┴────────────────┐
                          │         LangGraph Orchestrator  │
                          │   Planner ──► Researcher        │
                          │        └──► ToolExec ──┐         │
                          │        ┌── Critic ◄─────┘        │
                          └───┬───────┬────────┬────────────┘
                              │       │        │
                         PostgreSQL  Qdrant   vLLM (Mistral-7B)
                         (auth,    (vector    + LiteLLM router
                          convos,   store)     + fallback)
                          docs, usage)
                              │
                           Redis/Celery (ingestion queue, sessions)
```

## Repository layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI service, LangGraph graph, agents, tools, memory, ingestion |
| `frontend/` | Next.js 14 App Router, TypeScript, Tailwind CSS streaming chat |
| `finetune/` | Dataset build + LoRA/QLoRA training + eval + export to vLLM |
| `infra/` | Docker images + compose, Terraform, Kubernetes, nginx SSE proxy, Prometheus/Grafana |
| `docs/` | Full system design documentation (20 sections) |
| `.github/workflows/` | CI (ruff/mypy/pytest) and CD pipelines |

## Backend structure

```
backend/app/
├── main.py            # FastAPI app factory, middleware, Prometheus /metrics
├── config.py          # Pydantic settings (env-driven, no secrets in code)
├── api/               # Versioned REST API under /api/v1
│   └── v1/            # auth, documents, conversations (SSE stream), usage, health
├── agents/            # Planner, Researcher, Tool Executor, Critic specs + nodes
├── graph/             # AgentState, StateGraph + conditional routing, checkpointer, SSE events
├── orchestrator/      # Streaming bridge: LangGraph astream_events -> FastAPI SSE
├── tools/             # Typed tool primitive, catalog, registry, approval gates
├── memory/            # Token-budget summarizer, long-term store, context helpers
├── models/            # vLLM OpenAI-compatible gateway + LiteLLM fallback + cost accounting
├── services/          # Storage, embeddings, Qdrant vectorstore
└── ingestion/         # Celery pipeline, text parsers (pdf/docx/txt/csv), chunking
```

### API surface (all `/api/v1`)

| Method | Path | Description |
|---|---|---|
| GET | `/health/live`, `/health/ready` | Liveness / readiness probes |
| POST | `/auth/register`, `/auth/login`, `/auth/refresh` | JWT auth (access + refresh) |
| POST | `/auth/logout` | Invalidate session (204) |
| POST | `/workspaces/{ws}/documents` | Async document ingestion (202, Celery) |
| GET | `/workspaces/{ws}/documents` | List ingested documents |
| GET | `/workspaces/{ws}/documents/{id}/download` | Fetch original file |
| POST | `/workspaces/{ws}/conversations` | Create conversation |
| GET | `/workspaces/{ws}/conversations/{id}` | Conversation metadata |
| POST | `/workspaces/{ws}/conversations/{id}/messages/stream` | **SSE** chat stream |
| GET | `/workspaces/{ws}/conversations/{id}/messages` | Message history |
| GET | `/workspaces/{ws}/usage/summary` | Token + cost usage summary |
| GET | `/metrics` | Prometheus scrape endpoint |

### Data model

- **PostgreSQL** — users, workspaces, conversations, messages, documents,
  usage records; SQLAlchemy 2.0 + Alembic migrations; LangGraph checkpointing
  for conversation resumes.
- **Qdrant** — tenant-isolated vector store for semantic retrieval over
  ingested documents.
- **Redis** — sessions/cache; **Celery** — background ingestion pipeline.
- **S3/MinIO** — object storage for uploaded source files.

## Frontend

Next.js 14 App Router with TypeScript and Tailwind:

```
frontend/app/
├── layout.tsx          # Root layout + globals
├── page.tsx            # Landing / redirect
├── login/page.tsx      # JWT login
├── chat/page.tsx       # Streaming chat UI (SSE)
frontend/lib/auth-hook.ts     # Token storage + fetch wrapper
frontend/components/ChatWindow.tsx
```

The UI has a login page but **no registration form** — create an account via
the API before logging in (see the Docker quick start below).

## Fine-tuning (`finetune/`)

A self-contained LoRA/QLoRA pipeline:

1. **Dataset build** — instruction/follow-up/tool traces assembled for the
   domain (`finetune/data`, `finetune/src`).
2. **Training** — QLoRA 4-bit Mistral-7B configs in `finetune/configs`.
3. **Eval** — harness comparing LoRA vs. pretrained baseline.
4. **Export/serve** — export adapter and serve through vLLM (OpenAI-compatible).

See `docs/09-fine-tuning.md` for the full pipeline and the ~40% inference-cost
case, and `finetune/README.md` for the local workflow.

## Infrastructure (`infra/`)

- **Docker** — images and the dev stack live in `infra/docker/`
  (`docker-compose.yml` + `backend.Dockerfile`, `worker.Dockerfile`,
  `frontend.Dockerfile`).
- **Terraform** — AWS (RDS, Redis, S3, ECS/EKS), IaC for prod.
- **Kubernetes** — manifests for stage/prod, blue-green/canary rolling deploys.
- **nginx** — SSE proxy config (buffering disabled for streaming).
- **Monitoring** — Prometheus `/metrics` + Grafana dashboards, correlated
  request IDs, structured `structlog` output.

## CI/CD (`.github/workflows/`)

- `ci.yml` — runs `ruff`, `mypy`, `pytest` on the backend and `next lint` +
  `tsc` on the frontend.
- `cd.yml` — build + push images, deploy to EKS.

## Quick start

Prerequisites: Python 3.11+, `uv`, Node.js 18+, and Docker Desktop (for the
full stack).

### Full stack with Docker (recommended)

```bash
# 1. Prepare environment files
cp backend/.env.example backend/.env            # local dev defaults
cp backend/.env.example backend/.env.docker     # Docker overrides hosts to service names
```

> **Important:** in `backend/.env.docker`, all `*_URL` / `*_HOST` values must
> use the Docker service names (`postgres`, `redis`, `qdrant`, `minio`) instead
> of `localhost`, because containers resolve each other by name on the compose
> network. A ready-to-use `.env.docker` is committed next to `.env.example`.

```bash
# 2. Build and start the whole stack (postgres, qdrant, redis, minio, backend, worker, frontend)
docker compose -f infra/docker/docker-compose.yml up -d --build

# 3. Apply database migrations
docker compose -f infra/docker/docker-compose.yml exec backend alembic upgrade head

# 4. Create your account (the UI has no registration form)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"admin123","full_name":"Admin"}'
```

Then open:

| Service | URL | Credentials |
|---|---|---|
| Frontend app | http://localhost:3000 | your registered account |
| API docs (Swagger) | http://localhost:8000/docs | — |
| Qdrant dashboard | http://localhost:6333/dashboard | — |
| MinIO console | http://localhost:9001 | `minioadmin` / `minioadmin` |

Useful commands:

```bash
docker compose -f infra/docker/docker-compose.yml ps        # status
docker compose -f infra/docker/docker-compose.yml logs -f backend   # backend logs
docker compose -f infra/docker/docker-compose.yml down      # stop everything
```

> **Chat requires an LLM.** The orchestrator talks to vLLM
> (`VLLM_BASE_URL` in `.env`/`.env.docker`, currently pointing at the gateway)
> and falls back to `gpt-4o-mini` via LiteLLM. Start a vLLM server or set a
> valid `OPENAI_API_KEY` (via LiteLLM env vars) before sending chat messages.

### Local development (without Docker)

#### Backend

```bash
cd backend
uv sync --extra dev
cp .env.example .env          # fill in secrets (see backend/.env.example)
uv run alembic upgrade head   # apply migrations against a local Postgres
uv run uvicorn app.main:app --reload --port 8000
```

Health check: `curl localhost:8000/api/v1/health/live`
OpenAPI docs: `http://localhost:8000/docs`

#### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:3000
```

#### Local tests

```bash
cd backend
uv run pytest backend/tests        # API smoke, graph, tools, chunkers, security
uv run ruff check backend
uv run mypy backend
```

## Model routing & cost control

The LLM gateway (`backend/app/models/gateway.py`) talks to vLLM first
(self-hosted `conductor/mistral-7b`). On failure, or when budget/confidence
dictates, it falls back to a frontier model via LiteLLM. Every completion
returns token usage and estimated USD so the orchestrator records a per-agent
`UsageRecord`, exposed through `/usage/summary`. The full economics model,
including the ~40% inference-cost reduction case, is in
`docs/09-fine-tuning.md` and `docs/16-cost-optimization.md`.

## Documentation

A complete A-to-Z system design lives in `docs/` (20 sections):

- **Engineering spine:** `01-problem.md`, `02-architecture.md`,
  `09-fine-tuning.md`, `10-rest-api.md`, `11-database.md`, `12-security.md`
- **Agent system:** `05-langgraph-system.md`, `06-agent-design.md`,
  `07-tool-calling.md`, `08-memory-architecture.md`, `20-code-flow.md`
- **Ops & scale:** `13-deployment.md`, `14-monitoring.md`,
  `15-scalability.md`, `16-cost-optimization.md`
- **Storytelling:** `17-interview-prep.md`, `18-resume-justification.md`
- **Reference:** `00-README.md`, `03-tech-stack.md`,
  `04-user-interaction-flow.md`, `19-folder-structure.md`

Start at [`docs/00-README.md`](docs/00-README.md).

## Roadmap / status

- [x] Backend: graph, agents, tools, memory, model gateway, ingestion, API
- [x] Frontend: App Router chat scaffold with auth hook and streaming UI
- [x] Distribution: Docker, Terraform, K8s, nginx, monitoring, CI/CD
- [x] Docs: all 20 design sections
- [x] Docker stack verified end-to-end: build, run, migrate, register, login
- [x] Production database migrations applied against a running PostgreSQL
- [ ] Runtime model serving (vLLM) and frontier fallback wiring to a live key
- [ ] End-to-end streaming smoke test (load a doc → chat against it)
- [ ] Registration UI on the frontend (currently API-only)

