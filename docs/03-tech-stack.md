# 03 — Complete Tech Stack and Rationale

Every technology, why it was selected, and the alternatives we rejected.

## Frontend

| Tech | Selected? | Alternatives rejected | Why |
|---|---|---|---|
| Next.js (App Router) | ✅ | Remix, Vite+SPA | SSR, streaming, edge-friendly, typed routes; React Server Components |
| React 18+ | ✅ (bundled) | — | RSC + concurrent streaming for chat UX |
| TypeScript (strict) | ✅ | JS | shared enum/event shapes across the SSE contract |
| Tailwind CSS | ✅ | CSS modules, styled-components | fast iteration, design tokens, no runtime CSS-in-JS |
| SSE (EventSource) | ✅ | WebSockets, fetch polling | one-directional AI streaming; proxy-friendly, resumable |

## Backend

| Tech | Why | Alternatives |
|---|---|---|
| Python 3.11+ | LangGraph + ML ecosystem in one runtime | TS/Node runtime |
| FastAPI | typed, async, Pydantic v2, OpenAPI out of the box, SSE-native | Django/Flask (sync, heavier) |
| Pydantic v2 | typed schema, validation, JSON schema source of truth | marshmallow, attrs |
| SQLAlchemy 2.0 | typed mapped columns + Alembic migrations | raw SQL, Peewee |
| structlog | structured JSON logs with correlation ids | stdlib logging, loguru |
| uvicorn | ASGI server for FastAPI | hypercorn, gunicorn+uvicorn workers |

## AI layer

| Technology | Why | Alternatives |
|---|---|---|
| LangGraph | explicit state machine: nodes, conditional edges, checkpoints, interrupts (HITL), streaming | LangChain agents (implicit, hard to control), hand-rolled orchestration |
| Hugging Face Transformers | weights, tokenizers, training utilities | custom inference code |
| Mistral-7B-Instruct-v0.3 | 7B, Apache-2.0, strong instruction following, cheap to serve on 1 GPU | Llama-3-8B (heavier), Llama-2, GPT-4 class (hosted-only) |
| LoRA / QLoRA | train a small adapter (rank 16); QLoRA adds NF4 quantization for a 5.5GB working set | full fine-tuning (needs A100-class GPU, expensive, overfits) |
| vLLM | continuous batching, PagedAttention KV cache, OpenAI-compatible API, NF4 deployment | TGI (no NF4 batched), Ollama (local/dev only, no auto batch), DeepSpeed (op-heavy) |
| LiteLLM | model routing, fallback, cost gating across providers | hand-rolled multi-client |
| Sentence Transformers (BGE) | self-hosted embeddings, onnxruntime | OpenAI embeddings (per-token cost, privacy), TF Hub |
| Qdrant | vector store with payload filters (tenant isolation), fast filterable search | Pinecone ($$, vendor lock), Weaviate (heavier ops), FAISS (self-managed, no server) |

## Storage & messaging

| Technology | Why | Alternatives |
|---|---|---|
| PostgreSQL 16 | relational core + JSONB + LangGraph `PostgresSaver` checkpoints + Alembic | MySQL (JSONB/ENUMs weaker) |
| Redis | cache, session, rate-limiter, Celery broker, pub/sub for SSE fan-out | RabbitMQ (Kafka needed later only for 100k) |
| Celery | Python task queue with routed queues (`ingestion`, `embedding`) | RQ, Dramatiq, BullMQ |
| S3 (MinIO dev) | object store + presigned URLs, cheap GB | EFS (latency/cost) |
| LangGraph `PostgresStore` | long-term memory store | in-memory only (lost on restart) |

## Cloud & DevOps

| Technology | Why |
|---|---|
| AWS | managed RDS/S3/EKS/CloudFront/ECR; compliance posture |
| EKS (with Fargate for CPU, node group for GPU) | containerized autoscaling, k8s for service mesh later |
| EC2 GPU (g5/A10G, spot + on-demand mix) | cost-effective Mistral-7B serving (see `docs/16-cost-optimization.md`) |
| Terraform | infrastructure as code, reviewable diff, drift control |
| GitHub Actions | PR gates (ruff, mypy, pytest), image build, canary deploy |
| Nginx ingress | TLS, SSE idle timeout tuning, gzip, connecting FastAPI + WebUI |
| Docker | reproducible unit, CPU-heavy worker attach parity |

## Observability

| Technology | Role |
|---|---|
| Prometheus | metrics from FastAPI, Celery, vLLM |
| Grafana | dashboards + alert rules |
| Loki | logs from all pods |
| OpenTelemetry | trace ingestion (OpenTelemetry Collector) |
| Langfuse | LLM traces: prompts, tokens, cost, quality scores |
| CloudWatch | S3/RDS alarms, cost anomalies |

## Explicitly rejected

- **MongoDB** — no document workload; PG JSONB covers metadata.
- **Kafka day one** — correct at ~10–20k conversations/day; Redis + Celery
  suffices, then migrate (see `docs/15-scalability.md`).
- **Ollama** — great for laptops; no production scaling/batching guarantees.
- **GraphQL** — SSE REST is simpler and better for streaming-first.
- **In-process FAISS for prod** — no filters/server; Qdrant chosen.