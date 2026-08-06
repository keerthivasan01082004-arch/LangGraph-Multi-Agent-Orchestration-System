# 01 — Real-World Problem

## The business problem

Knowledge work produces slow, expensive research. Analysts at finance, legal,
support, and procurement teams spend 40–60% of their day retrieving
information scattered across wikis, PDFs, CRMs, and live systems, then
synthesizing it into answers that must be *correct* (citable) — before any
action is taken (email a client, file a record, run a query).

Generic single-shot chat assistants fail here for four reasons:

1. **No groundedness** — they answer from parametric memory, not your docs.
2. **No planning** — complex, multi-step questions get flattened into one call.
3. **No live tools** — they cannot query your CRM, the weather, tickers, or a DB.
4. **No verification** — nobody checks the draft before it ships to a user.

Conductor fixes all four by decomposing each request into a **Planner →
Researcher → Tool Executor → Critic** pipeline where every claim is
attributed and every side effect is approved.

## Who the users are

| Persona | Job | Pain Conductor removes |
|---|---|---|
| **Analyst** (finance) | Weekly reporting, market research | Hours of copy-pasting from 12 sources |
| **Support lead** | Answer client escalations | Inconsistent, uncited answers; SLAs missed |
| **Legal Ops / GRC** | Answer compliance questions against policies | Missing every "where did you find that?" |
| **Procurement** | Price + contract comparisons | Manual spreadsheet-driven research |
| **Workspace admin** | Owns data, budgets, access | No visibility into what models cost/do |

## Why companies pay

- **Faster answers with citations** → support deflection, faster closes.
- **Trust**: every claim links to the source document (auditable).
- **Safety**: emails/SQL/writes require a human approval step.
- **Predictable cost**: ~40% cheaper inference than a GPT-4-class baseline on
  the same workload (see sections 09 and 16).

Pricing is usage based: per-token agent time + per-seat. A $/seat tier for
on-demand. Unit economics are strong because the fine-tuned model is ~40%
cheaper than the fallback frontier model *and* the critic loop keeps quality
above the bar.

## Business workflow

```mermaid
flowchart LR
    A[Sign up / invite] --> B[Create workspace]
    B --> C[Connect data: upload docs / connect CRM+DB + live tools]
    C --> D[Ingestion: parse → chunk → embed → Qdrant]
    D --> E[Ask a question]
    E --> F[Planner makes a plan]
    F --> G[Researcher retrieves evidence]
    G --> H[Tool executor calls APIs / DB]
    H --> I[Critic scores the draft]
    I -->|reject| G
    I -->|approve| J[Streamed answer with citations]
    J --> K[User gave feedback; finance verifies cost]
```

## User journey — login to answer

```
1. Sign up via email + password (or SSO)
2. Create / join a workspace (tenant)
3. Upload documents (drag-and-drop; validated pdf/docx/csv)
4. Status: validating → processing → ready (async, SSE progress)
5. Pick a conversation, type a question
6. LangGraph starts: planner → researcher → tool executor → critic
7. Tokens stream to the browser live (SSE)
8. Answer ends with numbered citations + confidence score
9. Optional: admin/approver reviews a "send email" step before it executes
10. Every turn writes usage rows → cost dashboard updates in ~10s
```

## Outcome metrics

- ↑ Researchable questions per analyst / day
- ↓ Time-to-answer (median) and ↓ uncited claims (hallucination proxy)
- ↓ Inference $/answer vs. frontier model via the fine-tuned Mistral-7B