# 15 — Scalability

How the system scales from 100 to 1M users, and where the bottlenecks are at
each stage.

## 1. Growth stages and actions

| Stage | Users | System | Primary bottleneck | Action taken |
|---|---|---|---|---|
| S1 | 100 | single box (docker compose + 1 GPU) | none | baseline; dev parity |
| S2 | 1,000 | PG + Redis, 1 vLLM GPU | first GPU saturation | +1 vLLM replica; HPA on API |
| S3 | 10,000 | PG + Redis + Qdrant, GPU pool (3–5 A10G) | queue burst on ingestion | KEDA autoscaling on Celery; embedding queue split |
| S4 | 100,000 | partitioned PG + read replicas | write throughput on usage/messages | monthly range partitions, pgbouncer, read replica for dashboards |
| S5 | 1,000,000 | sharded data plane + regional edge | global fan-out / cross-region latency | multi-region edge, queue upgrade (Kafka), per-region GPU pools |

## 2. Bottleneck-by-component analysis

### API (stateless)
- Scales horizontally trivially: JWT auth means no sticky sessions.
- HPA 1→20 pods on CPU + latency; SSE streams hold connections, not threads.
- Per-pod connection limit for SSE (e.g. 512) with a stream budget metric.

### PostgreSQL
- Writes: usage records + messages dominate. Monthly range partitions keep
  indexes hot and deletes fast (`docs/11`).
- Reads: dashboards go to a read replica; pgBouncer for connection pooling.
- At S5: per-region primary with streaming replication; conversation tables
  tenant-sharded by `workspace_id` hash if a single writer saturates.

### Redis
- Used for cache + rate limits + Celery broker. Horizontal: cluster mode with
  key slots by user/workspace; memory-bound → increase node count.

### Qdrant
- One collection, tenant-filtered payloads. Scales via replicas (read
  scaling) then sharding at > ~100M vectors.
- Move payloads `on_disk_payload=true` for large corpora; keep vectors in RAM.

### Inference (the scarce resource)
- GPU concurrency ≈ `max_batch / seq_len`; vLLM continuous batching packs
  requests. KEDA scales vLLM pods on queue depth.
- Spot instance pools for non-latency-critical research batches; on-demand
  warm standby for real-time.

### Ingestion workers
- Celery queue `ingestion` + `embedding`; KEDA scales on queue length;
  embeddings batch per GPU chunk; large uploads are processed in chunks with
  `task_acks_late` for crash safety.

## 3. Back-of-envelope capacity math

Assumptions for 1M users:

| Assumption | Value |
|---|---|
| daily active | 10% (100k) |
| conversations / active user / month | 4 |
| conversations / day | ~13k |
| agent model calls / conversation | ~8 |
| avg tokens / call | 5k |
| total tokens / day | ~520M |

- **Token spend** at fine-tuned 7B self-hosted cost (~$0.08/M mixed tokens):
  ≈ **$42/day** in inference economics — the reason self-hosting matters.
- **Qdrant**: 100 GB corpus, dim 384 → ~2.5 GB of vectors; in-memory is fine.
- **PG**: ~13k conversations/day → 4.7M rows/year; partitioned, trivially fine.

## 4. Scaling decisions with trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| HPA + KEDA over manual scaling | elastic cost | cold-start latency on scale-up |
| Redis → Kafka only at S5 | KISS until the event volume demands it | replay/ordering limitations before that |
| Qdrant replicas before sharding | cheap read scaling | writes to every replica |
| Spot for batch, on-demand for realtime | 60–70% GPU cost cut | spot reclaims need queue-retry wiring |
| SSE kept over WebSockets | proxy-friendly, resumable, simpler | no server-initiated push beyond stream |

## 5. Load test & verification

- `k6` / `locust` scenarios: chat streaming, upload storm, concurrent 1k SSE.
- Assert SLOs from `docs/14` hold; soak for GPU memory leaks (vLLM known to
  hold steady with right `--max-paddings`).
- Chaos: kill a vLLM pod mid-stream → client reconnects, thread resumes via
  checkpoint.