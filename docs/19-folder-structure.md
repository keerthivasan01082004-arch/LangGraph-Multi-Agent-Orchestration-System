# 19 — Folder Structure

Production-grade repository layout. Paths mirror this repo exactly.

```
LangGraph-Multi-Agent-Orchestration-System/
├── AGENTS.md                      # agent coding conventions
├── LICENSE
├── README.md                      # project overview + architecture snapshot
├── backend/                       # Python 3.11 · FastAPI
│   ├── pyproject.toml             # uv-managed; ruff/mypy/pytest config
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── 0001_initial.py
│   ├── app/
│   │   ├── main.py                # FastAPI factory + lifespan + /metrics
│   │   ├── config.py              # pydantic-settings (all env)
│   │   ├── api/
│   │   │   ├── router.py          # /api/v1 composite router
│   │   │   ├── deps.py            # JWT auth + RBAC + tenant scoping
│   │   │   └── v1/
│   │   │       ├── auth.py        # register / login / refresh / logout
│   │   │       ├── conversations.py  # create, get, list, SSE stream
│   │   │       ├── documents.py      # upload + listing + presigned download
│   │   │       ├── usage.py          # cost/token aggregation
│   │   │       └── health.py         # /health/live /health/ready
│   │   ├── core/
│   │   │   ├── security.py        # JWT (access+refresh) + bcrypt
│   │   │   ├── errors.py          # ApiError framework + handlers
│   │   │   ├── middleware.py      # access log + correlation id + metrics
│   │   │   ├── metrics.py         # Prometheus counters/histograms/gauge
│   │   │   └── logging.py         # structlog JSON
│   │   ├── db/
│   │   │   ├── models.py          # ORM (users, workspaces, docs, convos, msgs, usage, audit)
│   │   │   └── session.py         # engine + SessionLocal
│   │   ├── schemas/
│   │   │   └── user.py            # Pydantic v2 request/response
│   │   ├── graph/
│   │   │   ├── state.py           # AgentState TypedDict (accumulated channels)
│   │   │   ├── builder.py         # StateGraph.compile(checkpointer, store)
│   │   │   ├── checkpointer.py    # PostgresSaver + PostgresStore (lazy)
│   │   │   ├── event.py           # SSE event payload builders
│   │   │   └── routes.py          # conditional routing predicates
│   │   ├── agents/
│   │   │   ├── nodes.py           # planner/researcher/executor/critic/finalizer
│   │   │   └── specs.py           # declarative agent metadata
│   │   ├── tools/
│   │   │   ├── base.py            # Tool dataclass + jsonschema validation
│   │   │   ├── registry.py        # ALL_TOOLS / SAFE_TOOLS + openai schema
│   │   │   └── definitions.py     # tool implementations (calc, weather, search…)
│   │   ├── memory/
│   │   │   ├── context.py         # summarization + eviction + token budget
│   │   │   └── store.py           # long-term fact store facade
│   │   ├── orchestrator/
│   │   │   └── service.py         # astream_events → SSE bridge + persistence
│   │   ├── models/
│   │   │   ├── gateway.py         # vLLM OpenAI client + LiteLLM fallback + pricing
│   │   │   └── cost.py            # UsageRecord persistence per agent call
│   │   ├── ingestion/
│   │   │   ├── parsers.py         # pdf/docx/txt/csv extraction
│   │   │   └── chunkers.py        # token-aware chunking + token_count
│   │   ├── services/
│   │   │   ├── storage.py         # S3 put/get/presign
│   │   │   ├── embeddings.py      # sentence-transformers batch encode
│   │   │   └── vectorstore.py     # Qdrant upsert/search/delete (tenant filter)
│   │   └── workers/
│   │       ├── celery_app.py      # Celery + task routes
│   │       └── tasks.py           # process_document → embed_chunk_batch
│   └── tests/
│       ├── conftest.py            # env bootstrap for pydantic-settings
│       ├── test_api.py            # health/metrics/error envelope
│       ├── test_chunkers.py
│       ├── test_graph.py          # routing predicates + builder topology
│       ├── test_security.py       # JWT roundtrip / expiry / typos
│       └── test_tools.py          # registry, calculator sandbox, approval flags
├── frontend/                      # Next.js 14 (App Router, TS, Tailwind)
│   ├── package.json / tsconfig.json / tailwind.config.ts / next.config.mjs
│   ├── app/
│   │   ├── layout.tsx  globals.css
│   │   ├── page.tsx              # landing
│   │   ├── login/page.tsx          # username/password → JWT storage
│   │   └── chat/page.tsx           # streaming chat shell
│   ├── components/
│   │   └── ChatWindow.tsx          # SSE consumer + token rendering
│   └── lib/
│       └── auth-hook.ts            # bearer token from localStorage
├── finetune/                      # Mistral-7B QLoRA pipeline
│   ├── pyproject.toml / README.md / .env.example
│   ├── configs/
│   │   ├── qlora.yaml
│   │   └── vllm.yaml
│   ├── data/raw/sample.jsonl        # synthetic seed examples
│   └── src/
│       ├── dataset.py               # clean → structured → split
│       ├── train_qlora.py          # PEFT/TRL trainer (NF4)
│       ├── eval.py                 # validity + faithfulness metrics
│       ├── export_merged.py        # merge adapters → registry
│       └── serve_vllm.py           # one-shot serving snippet
├── infra/
│   ├── docker/
│   │   ├── backend.Dockerfile / worker.Dockerfile / frontend.Dockerfile
│   │   └── docker-compose.yml       # postgres+qdrant+redis+minio+api+worker
│   ├── terraform/
│   │   ├── main.tf                  # RDS, ElastiCache, S3, ECR, ECS, ALB
│   │   └── network.tf               # SG + target group + cache subnet
│   ├── k8s/
│   │   ├── backend-deployment.yaml / backend-hpa.yaml / worker-deployment.yaml
│   ├── nginx/api.conf               # SSE-friendly proxy
│   └── monitoring/
│       ├── prometheus.yml  grafana-datasources.yml  grafana-dashboard.json  alerts.yml
├── .github/workflows/
│   ├── ci.yml                       # ruff · mypy · pytest · tsc
│   └── cd.yml                       # ECR push → staging → prod canary
└── docs/                            # 00–20 system design sections
```

Key conventions enforced by this layout:

- **Ownership**: `graph/` = orchestration only; `agents/` = decision logic;
  `tools/` = capability; `memory/` = persistence of state/knowledge.
- **Clean boundaries**: API never imports agent internals; tests import
  surfaces (`orchestrator/service.py`) not private internals.
- Config in **one place** (`config.py`), secrets only via env.