# 02 — Complete System Architecture

## System context (C4 L1)

```mermaid
flowchart LR
    U[Analyst / Admin] -->|HTTPS/SSE| F[Next.js Frontend]
    F --> CDN[CloudFront]
    CDN --> GW[FastAPI Gateway + API Gateway]
    GW --> ORCH[Orchestrator]
    ORCH --> AUTH[Auth Service]
    ORCH --> INGEST[Ingestion Pipeline]
    ORCH --> AGENT[LangGraph Agents]
    AGENT --> DB[(PostgreSQL)]
    AGENT --> VEC[(Qdrant)]
    AGENT --> LLM[vLLM · Mistral-7B]
    AGENT --> LLM2[Fallback: GPT-4o-mini]
    ORCH --> CACHE[(Redis)]
    ORCH --> OBJ[(S3)]
    ORCH --> MON[Prometheus · Langfuse · Loki]
```

## Container diagram (C4 L2)

```mermaid
flowchart TB
    subgraph Edge
        CF[CloudFront + WAF]
        ALB[Nginx / ALB]
    end
    subgraph front[Frontend tier]
        F[Next.js 14]
    end
    subgraph api[API tier — ECS Fargate]
        AUTH[FastAPI · auth]
        GATE[FastAPI · conversations/gateway]
        DOCAPI[FastAPI · documents]
        USAGE[FastAPI · usage]
    end
    subgraph orchest[Orchestration tier]
        GRAPH[LangGraph state machine]
        AGENTS[Planner · Researcher · Executor · Critic]
        TOOLS[Tool registry]
        MEM[Memory: checkpoint + Store]
    end
    subgraph workers[Celery workers]
        W1[ingestion queue]
        W2[embedding queue]
        W3[usage/analytics]
    end
    subgraph data[Data tier]
        PG[(PostgreSQL 16)]
        RD[(Redis 7)]
        QD[(Qdrant)]
        S3[(S3 documents)]
    end
    subgraph ai[Inference tier — EC2 g5 spot]
        VLLM[vLLM · Mistral-7B 4-bit]
        EMB[Embeddings · BGE/TEI]
    end

CF --> F
    F --> GW2[FastAPI Gateway]
    GW2 --> GATE[API Gateway]
    GATE --> AUTH
    GATE --> DOCAPI
    GATE --> GRAPH --> AGENTS
    AGENTS --> TOOLS
    AGENTS --> MEM
    AGENTS --> LLM
    GRAPH --> PG
    AGENTS --> QD
    W1 --> PG
    W2 --> QD
```

## Runtime architecture

```mermaid
flowchart LR
    B[Browser] -->|HTTPS + SSE| NG[Nginx]
    NG --> API[FastAPI]
    API -->|PostgresSaver| PG[(PostgreSQL)]
    API -->|Qdrant client| QD[(Qdrant)]
    API -->|OpenAI-compatible| VV[vLLM Mistral-7B]
    VV -->|fallback| FM[LiteLLM → GPT-4o-mini]
    API -->|enqueue| RD[(Redis → Celery)]
    CEL[Celery workers] -->|embed| QD
    CEL -->|chunks| PG
    API -->|presigned| S3[(S3)]
    API -->|telemetry| OTEL[Otel → Prometheus/Grafana/Langfuse]
```

## Design decisions

| Decision | Choice | Why |
|---|---|---|
| Orchestrator runtime | LangGraph (Python) | Explicit state machine, checkpointing, interrupts, Send-API parallelism |
| Sync + Async split | FastAPI sync routes, Celery for ingestion | Avoid CPU-heavy embedding in the request path |
| Single writer for answers | LangGraph `finalizer` node persists once | No duplicate/concurrent writes after streaming |
| Streaming | SSE (not WebSocket) | Fire-and-forget server→client; simple infra, proxies well |
| Model serving | vLLM (not TGI/Ollama) | Throughput + continuous batching + prefix caching at low cost |
| Fallback | LiteLLM → GPT-4o-mini | Escape hatch when fine-tuned model fails or is unavailable |

## Deployment topology

```mermaid
flowchart LR
    subgraph AWS["AWS"]
        subgraph region[us-east-1]
            VPC[VPC]
            subgraph tier1[Web/API tier]
                ALB[ALB]
                API1[API · Fargate]
                API2[API · Fargate]
            end
            subgraph tier2[Data tier]
                RDS[(RDS Postgres)]
                RED[(ElastiCache)]
                QDR[(Qdrant on EC2/ECS)]
                S3[(S3)]
            end
            subgraph tier3[Inference]
                G[R[g5.2xlarge]]
            end
        end
    end
```