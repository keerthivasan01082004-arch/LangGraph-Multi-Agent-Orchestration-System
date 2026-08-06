# 02 — Complete System Architecture

High-level C4 representation of Conductor as deployed in production (AWS,
kubernetes, thousands of daily users).

## 1. Context diagram (Level 1)

```mermaid
C4Context
  title Conductor — System Context
  Person(user, "End user (analyst/ops/admin)", "Asks research questions, uploads docs, approves actions")
  Person(admin, "Workspace admin, finance, SE", "configures data, manages budget/rbac, monitors")

  System(conductor, "Conductor", "Multi-agent research & action assistant over your data")

  System_Ext(crm, "CRM / ERP / data warehouse", "authoritative business data via tools")
  System_Ext(idp, "Identity provider (Okta/Auth0)", "SSO, directory sync")
  System_Ext(hfhub, "Hugging Face Hub", "base weights + datasets")
  System_Ext(cloud, "Cloud GPU providers", "vLLM inference, embeddings")

  Rel(user, conductor, "HTTPS/SSE: upload, chat, approvals")
  Rel(admin, conductor, "HTTPS: admin UI, dashboards")
  Rel(conductor, crmse, "read-only tool calls (SQL/APIs)")
  Rel(conductor, idp, "OIDC / JWT")
  Rel(conductor, hfhub, "pull weights · datasets · eval sets")
  Rel(conductor, cloud, "GPU inference + embeddings")
```

## 2. Container diagram (Level 2)

```mermaid
C4Container
    title Conductor — Containers

    Person(user, "User browser session")
    Person(admin, "Admin session")

    Container(web, "Next.js frontend", "TypeScript / React App Router", "chat UI, workspace mgmt, billing, SSE client")
    Container(cdn, "CloudFront CDN / edge", "cache assets")

    Container(gw, "API Gateway (nginx / FastAPI)", "TLS, rate-limit, JWT verify, SSE pass-through")
    Container(api, "FastAPI service", "Python, async", "REST /api/v1, auth, docs, streams")
    Container(orchestrator, "LangGraph orchestrator", "Python / LangGraph", "state machine: planner→researcher→executor→critic")
    Container(worker, "Celery workers", "Python", "ingestion pipeline (parse, chunk, embed, index)")
    Container(inference, "vLLM Mistral-7B", "Python / vLLM", "OpenAI-compatible, KV cache, batching, continuous filling")
    Container(routes, "LiteLLM model router", "LLM routing + cost gates", "fine-tuned 7B primary, frontier fallback")

    ContainerDb(pg, "PostgreSQL", "users, workspaces, documents, conversations, messages, usage, audit, checkpoints")
    ContainerDb(redis, "Redis", "cache, Celery broker, rate counters, per-user sessions, SSE pub/sub")
    ContainerDb(qdrant, "Qdrant", "tenant-filtered vector store for retrieval")
    ContainerDb(objstore, "S3 / MinIO", "raw documents, presigned download URLs")

    Rel(user, web, "HTTPS / SSE")
    Rel(web, cdn, "HTTPS")
    Rel(cdn, gateway, "HTTPS")
    Rel(gateway, api, "HTTPS")
    Rel(api, orchestrator, "in-process orchestrate")
    Rel(api, worker, "Celery task enqueue")
    Rel(worker, objstore, "read / presign")
    Rel(worker, qdrant, "upsert chunks")
    Rel(orchestrator, inference, "OpenAI-compatible calls")
    Rel(orchestrator, routes, "LLM routing + fallback")
    Rel(orchestrator, pg, "checkpoints + usage")
    Rel(api, pg, "queries")
    Rel(api, redis, "cache / sessions / rate")
    Rel(gateway, cdn, "origin")
```

> Note: the C4 diagram above is deliberately schematic; the exact topology is
> cloud-native: gateway, API, workers, and image inference all run on EKS with
> HPA (or Fargate/EKS cost trade-off in `docs/13`).

## 3. Component diagram (Level 3) — the backend

```mermaid
flowchart TB
    subgraph edge
        CF[CloudFront]
        NG[API gateway / nginx]
    end
    subgraph svc[Stateless services]
        API[FastAPI /api/v1]
        ORC[LangGraph orchestrator]
        WK[Celery ingestion workers]
    end
    subgraph ai[LLM plane]
        VLLM[vLLM Mistral-7B<br/>LoRA/QLoRA · NF4]
        RT[LiteLLM router]
        EMB[Embedding server<br/>BGE · ONNX]
    end
    subgraph data[Data plane]
        PG[(PostgreSQL)]
        RD[(Redis)]
        QD[(Qdrant)]
        S3[(S3 object store)]
    end
    subgraph obs[Observability]
        PM[Prometheus]
        GR[Grafana]
        LG[Loki]
        LF[Langfuse]
        OT[OpenTelemetry]
    end

    S --> NG --> API
    API --> ORC
    API --> WK
    ORC --> RT
    ORC --> EMB
    ORC --> QD
    ORC --> PG
    API --> PG: usage, convos
    API --> RD: rate limit, session
    WK --> QD
    WK --> S3
    ORC -.traces.-> OT
    API -.logs/metrics.->obs
```

## 4. Data flow table

| # | Component | Responsibility | Storage |
|---|---|---|---|
| 1 | Next.js | UI, SSE client, optimistic chat | browser |
| 2 | Auth service | issue/verify JWT (access + refresh) | PG (users) + Redis (jti blocklist) |
| 3 | FastAPI | /api/v1 REST, validation, RBAC, SSE | PG, Redis |
| 4 | LangGraph | state machine, checkpoint, stream | PG checkpoints |
| 5 | Qdrant | semantic retrieval per workspace | vector index |
| 6 | vLLM | model serving with continuous batching | GPU |
| 7 | Celery | heavy ingestion jobs | Redis queue |
| 8 | S3 | documents, presigned downloads | object store |
| 9 | Prometheus/Grafana | metrics dashboards | TSDB |
| 10 | Langfuse | LLM traces, cost, quality | clickhouse |
| 11 | Loki | unstructured logs | log store |

## 5. Component decisions at a glance

| Decision | Choice | Why (short) |
|---|---|---|
| Backend | FastAPI | async-first, typed Pydantic v2, OpenAPI, SSE-native |
| Orchestration | LangGraph | explicit graph edges, checkpoints for HITL, streaming |
| Model serving | vLLM (self) | 40% cheaper, continuous batching, OpenAI-API compatible |
| Vector store | Qdrant | cheap self-host on EBC, filterable payload, fast |
| DB | PostgreSQL | transactional core + checkpoints 
| Cache/queue | Redis | low latency, many primitives |

Each box's production choice and the alternatives rejected are explained in
`docs/03-tech-stack.md`.