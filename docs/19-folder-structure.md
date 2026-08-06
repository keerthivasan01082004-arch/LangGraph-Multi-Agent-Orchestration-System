# 19 — Folder Structure

Production-grade repository layout mirroring this repo.

```
.
├── README.md
├── AGENTS.md
├── LICENSE
├── .gitignore
├── .github/
│   └── workflows/
│       ├── ci.yml               # ruff · mypy · pytest
│       └── deploy.yml          # build → ECR → canary/blue-green
│
├── backend/
│   ├── pyproject.toml          # uv project + ruff/mypy/pytest config
│   ├── Dockerfile
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/0001_initial.py
│   ├── app/
│   │   ├── main.py             # app factory, middleware bundle, /metrics
│   │   ├── config.py           # pydantic-settings
│   │   ├── api/
│   │   │   ├── router.py       # /api/v1 root
│   │   │   ├── deps.py         # get_current_user, get_workspace, require_role
│   │   │   └── v1/
│   │   │       ├── auth.py
│   │   │       ├── health.py
│   │   │       ├── documents.py
│   │   │       ├── conversations.py
│   │   │       └── usage.py
│   │   ├── core/
│   │   │   ├── security.py     # JWT + bcrypt
│   │   │   ├── errors.py       # typed APIError envelope
│   │   │   ├── logging.py      # structlog
│   │   │   ├── middleware.py   # correlation id, access log
│   │   │   └── metrics.py      # Prometheus
│   │   ├── db/
│   │   │   ├── models.py       # SQLAlchemy 2.0 ORM
│   │   │   └── session.py      # engine + SessionLocal
│   │   ├── schemas/user.py     # Pydantic contracts
│   │   ├── services/
│   │   │   ├── storage.py      # S3 abstraction
│   │   │   ├── embeddings.py   # BGE/ONNX
│   │   │   └── vectorstore.py  # Qdrant client
│   │   ├── ingestion/
│   │   │   ├── parsers.py      # pdf/docx/txt/csv
│   │   │   └── chunkers.py     # tiktoken, token_count
│   │   ├── workers/
│   │   │   ├── celery_app.py
│   │   │   └── tasks.py        # process_document, embed_chunk_batch
│   │   ├── tools/
│   │   │   ├── base.py         # Tool primitive (JSON-schema validated)
│   │   │   ├── definitions.py  # tool implementations
│   │   │   └── registry.py     # ALL_TOOLS, SAFE_TOOLS, approval policy
│   │   ├── agents/
│   │   │   ├── nodes.py        # planner/researcher/executor/critic/finalizer
│   │   │   └── specs.py        # AgentSpec registry
│   │   ├── graph/
│   │   │   ├── state.py        # AgentState
│   │   │   ├── builder.py      # StateGraph + conditional edges
│   │   │   ├── checkpointer.py # PostgresSaver / PostgresStore
│   │   │   └── event.py        # SSE event payloads
│   │   ├── memory/
│   │   │   ├── context.py      # summarize_messages / evict
│   │   │   └── store.py        # long-term remember/recall
│   │   ├── models/
│   │   │   ├── gateway.py      # vLLM OpenAI-compatible + LiteLLM fallback
│   │   │   └── cost.py         # persist_usage
│   │   └── orchestrator/
│   │       └── service.py      # run_conversation_stream (SSE bridge)
│   └── tests/
│       ├── test_chunkers.py
│       ├── test_security.py
│       ├── test_tools.py
│       └── test_graph.py
│
├── frontend/
│   ├── package.json
│   ├── next.config.mjs
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/               # App Router pages (chat, workspace, admin)
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx
│   │   │   └── (auth)/...
│   │   ├── api/                # fetch wrappers + SSE EventSource client
│   │   ├── components/chat/     # MessageList, Composer, ApprovalBanner
│   │   ├── lib/auth.ts         # middleware (JWT cookies)
│   │   └── types/api.ts        # generated from OpenAPI
│   └── Dockerfile
│
├── finetune/
│   ├── data/
│   │   ├── build_dataset.py
│   │   ├── clean.py            # dedupe / PII / normalization
│   │   └── schemas.py
│   ├── train/
│   │   ├── train_qlora.py      # PeFT+BitsAndBytes
│   │   └── configs/qlora-mistral-7b.yaml
│   ├── eval/
│   │   ├── eval_harness.py      # rubric + tool-call + format accuracy
│   │   └── golden_set.jsonl
│   └── serve/
│       ├── export_merge.py      # adapter → merged
│       └── vllm_serve.sh        # quantization nf4, served-model-name
│
├── infra/
│   ├── docker-compose.yml       # dev stack: api, worker, pg, redis, qdrant, minio
│   ├── docker/                  # per-service Dockerfiles
│   ├── terraform/
│   │   ├── environments/{dev,staging,prod}.tf
│   │   └── modules/            # vpc, rds, redis, qdrant, s3, eks, waf
│   ├── kubernetes/
│   │   ├── api-deploy.yaml + hpa
│   │   ├── worker-deploy.yaml + kedascale
│   │   ├── vllm-deploy.yaml + gpu
│   │   └── ingress.yaml        # nginx: SSE timeouts
│   ├── monitoring/
│   │   ├── prometheus.yml
│   │   ├── grafana/dashboards/*.json
│   │   ├── loki-config.yml
│   │   └── alerts/*.rules.yml
│   └── helm/                    # charts (or keep raw manifests)
│
└── docs/                        # this documentation set (00–20)
```

## Invariants this layout enforces

- **Boundaries**: `agents/` never talks to the DB; `services/` owns external
  I/O; `api/` owns HTTP; `graph/` owns state flow — keeps each layer
  independently unit-testable.
- **Secrets**: config only via env; `.env.example` is the contract.
- **Tests** run inside CI with no GPU/DB (checkpointer degrades to `None`).