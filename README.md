# Conductor — LangGraph Multi-Agent Orchestration System

A production-grade, enterprise multi-agent AI orchestration platform. Four
specialized agents — **Planner**, **Researcher**, **Tool Executor**, and **Critic** —
are orchestrated as an explicit LangGraph state machine to answer complex,
deep-research questions against your own documents and live tools.

The system is backed by a domain fine-tuned **Mistral-7B** (LoRA/QLoRA, 4-bit
quantization) served efficiently via **vLLM**, exposed through a versioned
**FastAPI** REST API, and fronted by a **Next.js** streaming chat UI.

---

## Why this exists

Single-shot LLM chat can't reliably do research that requires planning, live
tools, and critique. "Conductor" decomposes a request into a plan, executes
research and tool calls, and runs a critic pass before answering — with
citations, confidence, and human-in-the-loop approval for sensitive actions.

## Architecture at a glance

```
React/Next.js        →  CloudFront  →  FastAPI gateway
                                        │
                    ┌───────────────────┴──────────────────┐
                    │        LangGraph Orchestrator         │
                    │  Planner → Researcher → ToolExecutor   │
                    │              └── Critic ──┘            │
                    └──────┬─────────┬──────────┬───────────┘
                           │         │          │
                     PostgreSQL    Qdrant     vLLM (Mistral-7B)
                     (users,      (vector     + LiteLLM router
                      convos,      store)
                      docs, usage)
```

## Repository layout

| Path | Purpose |
|---|---|
| `backend/` | FastAPI service, LangGraph graph, agents, tools, memory, ingestion |
| `frontend/` | Next.js 14 App Router, TypeScript, Tailwind CSS |
| `finetune/` | Data pipeline + LoRA/QLoRA training + eval + export |
| `infra/` | Terraform, Kubernetes manifests, Docker, monitoring |
| `docs/` | Full system design documentation (20 sections) |
| `.github/workflows/` | CI/CD pipelines |

## Quick start (docs-first)

Full A-to-Z system design lives in [`docs/00-README.md`](docs/00-README.md).
For the backend:

```bash
cd backend
uv sync
cp .env.example .env          # fill in secrets
uvicorn app.main:app --reload
```

## License

MIT — see [LICENSE](LICENSE).