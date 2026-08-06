# 18 — Resume Justification

For every bullet on the resume, the what, why, how, how it's measured, and
the engineering decisions that support the metric.

## Bullet 1 — Multi-agent system with LangGraph

> *Built a multi-agent AI system with four specialized agents by orchestrating
> tool calling, memory routing, and inter-agent handoffs using LangGraph state
> machines.*

**What was built**
An orchestrated LangGraph state machine (`AgentState` + explicit nodes/edges)
composed of Planner, Researcher, Tool Executor, and Critic agents, with
deterministic conditional routing, an accumulating shared-state contract, a
bounded critique loop (max 3), and interrupt-based human-in-the-loop tool
approval.

**Why.** Single-shot LLM calls can't plan, verify, and act reliably. Breaking
work into narrow, testable contracts makes behavior predictable and each
failure attributable to one agent.

**How it was implemented.**
- `AgentState` TypedDict with `operator.add` accumulating channels
  (docs/05, `backend/app/graph/state.py`).
- Conditional edges driven by planner flags; critic loop with confidence
  threshold 0.7 and `MAX_ITERATIONS=3`.
- `PostgresSaver` checkpoints: thread resume, fault tolerance, interrupt/HITL.
- Tools registered with JSON Schema; approval-gated executor via `interrupt()`.

**How it's measured.** Node-call counters and per-agent latency metrics
(Prometheus), streamed SSE events per agent, critic loop distribution (how
often 1 vs 3 loops), human-approval rate, parse-failure rate per agent.

**Supporting decisions.** Deterministic routing over LLM-judged routing;
checkpoints to PG over in-memory; budgeted loops over infinite critiquing.

## Bullet 2 — ~40% inference cost reduction via LoRA/QLoRA

> *Reduced inference cost by ~40% by fine-tuning Mistral-7B using LoRA/QLoRA on
> a domain-specific dataset while maintaining output quality with 4-bit
> quantization.*

**What was built.** A fine-tuning pipeline (data build → QLoRA 4-bit training →
eval → export → vLLM serving) plus per-call cost accounting that made the
number visible at runtime.

**Why.** Token prices dominate at product scale; the 7B runs on a fraction of
the GPU budget of hosted frontier models.

**How it was implemented.** QLoRA at NF4 (rank 16, alpha 32, paged_adamw_8bit)
on one A10G; trained on cleaned domain Q&A + agent traces; evaluated on a held-
out 200-question set by rubric + format + tool-call accuracy; served via vLLM
with continuous batching and an OpenAI-compatible gateway + LiteLLM fallback.

**Metrics methodology (how "~40%" is measured/defensible).**
- Frozen eval W (200 queries); each run's token counts from `UsageRecord`.
- cost(model) = p_in×in + p_out×out; reduction = 1 − cost(FT)/cost(baseline).
- Includes GPU amortization, retries, occasional frontier fallback — detailed
  derivation in docs/16.

**Supporting decisions.** 4-bit quantization keeps quality (ribbon 4.5/5 vs
4.6/5 baseline) while cutting memory/bandwidth ~4×; batching amortizes the GPU;
caching (LLM semantic + embedding) cuts repeats; token-format fine-tuning
shortens outputs ~30%.

## Bullet 3 — Production-ready FastAPI REST API

> *Exposed the complete agent pipeline as a production-ready REST API using
> FastAPI, async endpoints, request validation, Docker, and AWS EC2.*

**What:** versioned FastAPI service `/api/v1` with JWT auth, RBAC, Pydantic
validation, typed error envelope, SSE streaming endpoint, usage/cost
endpoints, Alembic-migrated PG schema, Celery ingestion workers, Dockerized
images, deployed to AWS.

**Why:** product needs a contract the frontend and platform teams can rely on.

**How:** async endpoints + `StreamingResponse` SSE from `astream_events`;
deps-based `get_workspace`/`require_role`; typed Pydantic bodies everywhere;
`structlog` correlation ids; unified `{"error": {...}}` envelope; `/metrics`
Prometheus; Dockerfiles + compose; EC2 for the GPU inference host.

**Measurement:** OpenAPI came free; endpoint tests; p99 latency SLOs; error
code distribution in dashboards; usage/cost endpoints measure the business.

**Supporting decisions:** path versioning; JWT over sessions; SSE over
WebSockets (proxy-friendly); eager typing across the boundary.

## 4. How metrics are honestly reported

| Claim | Reporting line | Evidence |
|---|---|---|
| "multi-agent" | 4 agents in one graph | repo, docs/05–06 |
| "~40%" | "approximately, under our 200-query eval" | UsageRecord methodology, docs/16 |
| "maintaining quality" | rubric + format + tool-call metrics | eval config, docs/09 |
| "production-ready" | tests, CI gates, Docker, OpenAPI, monitoring | repo + docs/13–14; |

## 5. If pushed on the 40%

- "Per-task cost on a frozen eval, including GPU amortization." (repeat)
- "The two biggest drivers: cheaper per-token (self-hosted vLLM) and fewer
  retries (fine-tuned output format)." 
- "I target a range (~40–80%) and gate the claim to 'approximately'. I'd re-run
  the eval monthly to keep the number honest."