# System Design Documentation — Table of Contents

Complete A-to-Z design of the **Conductor** LangGraph multi-agent orchestration
system, written as it would exist in a real startup/enterprise production
environment serving thousands of daily users.

## How to read this

Read **00** once for context. Then either go deep path (01 → 09 → 10 → 11 → 12)
for the engineering spine, or use the surface path (10 → 13 → 14 → 15 → 16)
for operations. Sections 17 and 18 are interview focused.

---

## Index

| # | File | Covers |
|---|---|---|
| 00 | (this file) | Index, design contract, naming, numbers model |
| 01 | `docs/01-problem.md` | Real-world problem, personas, business workflow, user journey |
| 02 | `docs/02-architecture.md` | End-to-end architecture, C4 + system diagrams |
| 03 | `docs/03-tech-stack.md` | Every technology with selection rationale + alternatives |
| 04 | `docs/04-user-interaction-flow.md` | Step-by-step user + backend interaction flow |
| 05 | `docs/05-langgraph-system.md` | LangGraph states, transitions, routing, memory, HITL |
| 06 | `docs/06-agent-design.md` | Planner / Researcher / Tool Executor / Critic detailed specs |
| 07 | `docs/07-tool-calling.md` | Tool catalog, selection logic, safety |
| 08 | `docs/08-memory-architecture.md` | Short/long-term, vector, session, summarization, eviction |
| 09 | `docs/09-fine-tuning.md` | Mistral-7B LoRA/QLoRA pipeline A-to-Z, the ~40% cost case |
| 10 | `docs/10-rest-api.md` | Endpoints, request/response, auth, streaming, errors |
| 11 | `docs/11-database.md` | PostgreSQL + Qdrant schema, ER diagrams, indexes |
| 12 | `docs/12-security.md` | JWT/OAuth/RBAC, prompt injection, multi-tenancy |
| 13 | `docs/13-deployment.md` | Dev/stage/prod, Docker, EKS, GitOps, blue-green/canary |
| 14 | `docs/14-monitoring.md` | Prometheus/Grafana/Langfuse/Otel, dashboards, alerts |
| 15 | `docs/15-scalability.md` | 100 → 1M users, bottlenecks, scaling strategies |
| 16 | `docs/16-cost-optimization.md` | Model routing, caching, quantization, spot, token op |
| 17 | `docs/17-interview-prep.md` | Architecture story, trade-offs, expected Q&A, mistakes |
| 18 | `docs/18-resume-justification.md` | Each resume bullet → what/why/how/metrics |
| 19 | `docs/19-folder-structure.md` | Full production repository tree |
| 20 | `docs/20-code-flow.md` | Lifecycle of one request end-to-end |

---

## Design contract (single source of truth)

All sections reference this same concrete system:

- **Product name:** Conductor
- **Product:** Enterprise SaaS for deep research over your own data + live tools
- **Pricing:** usage-based (tokens) + per-seat tier; ~$0.25/1k tokens agent-time
- **Model spine:** Mistral-7B-Instruct-v0.3, LoRA/QLoRA, NF4 4-bit, vLLM
- **Cost claim to defend:** ~40% inference-cost reduction vs. pretrained,
  chat-optimized baseline at equal output quality
- **Four agents:** Planner, Researcher, Tool Executor, Critic
- **Storage:** PostgreSQL (relational), Redis (cache/queue), Qdrant (vectors),
  S3 (objects)
- **Deployment:** AWS ECS → EKS, Terraform, GitHub Actions, blue-green/canary
- **Language:** Python 3.11+ (backend), TypeScript/Next.js (frontend)

## Consistency rules

- Endpoint prefix: `/api/v1/`
- Auth: JWT (access + refresh), `Authorization: Bearer`
- Language names referenced across docs must match `docs/19-folder-structure.md`.