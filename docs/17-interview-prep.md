# 17 — Interview Preparation

Everything you need to defend this project: the 60-second pitch, the deep
dive, trade-offs, expected questions with strong answers, follow-ups, and
common mistakes.

## 1. The 60-second pitch

> "I built a multi-agent AI orchestration platform called Conductor. Four
> specialized agents — Planner, Researcher, Tool Executor, Critic — run as an
> explicit state machine on LangGraph: the planner decomposes the user's
> request, the researcher grounds it in a tenant-isolated vector store
> (Qdrant), the executor safely drives tools with human-in-the-loop approval
> for side effects, and the critic scores the draft and triggers revision
> loops. The model is a Mistral-7B I fine-tuned with QLoRA at 4-bit and serve
> through vLLM, which — combined with model routing and caching — gets us
> roughly 40% cheaper inference than a hosted frontier model at equal quality.
> It's exposed as a versioned FastAPI REST API with SSE streaming, JWT auth,
> RBAC, and usage-based cost accounting, deployed to AWS EKS with Terraform and
> GitHub Actions."

## 2. Architecture deep dive (what to draw on the whiteboard)

1. Draw the user → Next.js → API → LangGraph → vLLM/Qdrant/PG/Redis flow.
2. Draw the state graph: planner → conditional route → researcher/executor →
   finalizer → critic loop (max 3) → answer.
3. Point at the three hard problems and your solution:
   - **Streaming**: `astream_events` → SSE contract.
   - **Human-in-the-loop**: LangGraph `interrupt()` + checkpoint resume.
   - **Cost**: QLoRA NF4 + vLLM batching + router + semantic cache.

## 3. Trade-offs (memorize the "why not X")

| Decision | Why this | What you gave up |
|---|---|---|
| LangGraph over plain LangChain agents | explicit edges, checkpoints, interrupts | less turnkey "agent" magic |
| Self-hosted vLLM over API | 40% cost, data privacy | ops burden of GPUs |
| Qdrant over Pinecone | self-host cost + tenant payload filters | less managed |
| SSE over WebSockets | resumable, proxy-friendly, simple | no bidirectional push |
| 4 agents, fixed graph | predictable, testable | less flexible than fully dynamic planning |
| PostgresSaver checkpoints | durable resume + HITL | write amplification on DB |

## 4. Expected questions & strong answers

**Q: Why do you need multiple agents instead of one prompt?**
A: A single call has no loop: it can't verify, retry, or use tools safely. The
Planner/Researcher/Critic split gives each step a narrow contract, so failures
are detectable — the critic's score is a quality signal we can alert on, and
the planner's flags make routing deterministic and testable.

**Q: How do agents share state?**
A: One `AgentState` TypedDict flows through the graph. Accumulating channels
(`research_notes`, `tool_results`, `usage`) append with `operator.add`; scalars
overwrite. Every node returns a partial update, so the contract is explicit and
unit-testable.

**Q: How is human-in-the-loop implemented?**
A: Sensitive tools declare `needs_approval`. The executor calls LangGraph's
`interrupt()` before running them, the graph checkpoints mid-flight, and the
API surfaces a `human_approval` SSE event. Resuming sends `Command(resume=...)`.
This is durable — the checkpoint is in Postgres.

**Q: How did you measure the 40% cost reduction?**
A: I froze a 200-question eval workload, ran it on a hosted chat baseline and
on our fine-tuned 7B, and compared per-task cost from the `UsageRecord` cost
accounting we write on every agent call. The reduction comes from cheaper
tokens (self-hosted vLLM), fewer retries (better agentic format), shorter
outputs, and caching — the exact derivation is in docs/16.

**Q: What happens when vLLM is down?**
A: Gateway retries with backoff, then LiteLLM falls back to the frontier model
for the request, marking the fallback ratio in metrics. If fallback is
disabled, the stream returns a typed 503 with the correlation id for
investigation.

**Q: How do you keep tenants isolated?**
A: At three layers: every API query goes through a membership-checked
`get_workspace` dependency, Qdrant filters on `workspace_id` in the payload,
and S3 keys are workspace-prefixed with IAM restrictions. Isolation is
structural, not prompt-instructed.

**Q: Why fine-tune Mistral-7B instead of just prompting GPT-4o?**
A: At our volume, per-token cost dominates. QLoRA lets me train a domain
adapter for ~$100 of GPU time, and the 7B at 4-bit runs on one A10G. The
fine-tune also teaches the exact output formats (JSON plans, tool calls), which
reduces parse failures and retries.

**Q: How would you scale to 100× the traffic?**
A: API is stateless (HPA); the bottleneck is GPU and DB writes. GPUs scale via
KEDA on vLLM queue depth plus spot pools; usage/messages get monthly
partitions, dashboards move to a read replica, then per-region primaries at the
largest scale. (Walk the S1–S5 table from docs/15.)

## 5. Follow-up questions to expect

- "How do you prevent prompt injection?" → boundary + sanitization + tool
  policy + audit (docs/12).
- "How do you evaluate agent quality?" → rubric eval + golden set + Langfuse
  scores + critic score distribution.
- "How does memory work across sessions?" → checkpoints + PostgresStore +
  summarization (docs/08).
- "What would you change?" → move ingestion to Kafka at scale, add parallel
  research fan-out with `Send()`, distil to a smaller checkpoint.

## 6. Common mistakes (don't do these)

1. Claiming 40% without a methodology — always anchor to the frozen eval.
2. Describing LangGraph as "LangChain agents" — they're different; you control
   edges explicitly.
3. Hand-waving HITL — be precise: `interrupt()`, checkpoints, `Command(resume)`.
4. Ignoring tenant isolation in the answer — interviewers check security
   instinct.
5. Saying "the GPU did X" without numbers — bring the token math.
6. Overclaiming metrics: use "approximately 40% under our eval" not "40% savings".
7. Not knowing your own endpoints — rehearse the API table from docs/10.