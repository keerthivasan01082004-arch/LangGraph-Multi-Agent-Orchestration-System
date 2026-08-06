# 15 — Scalability

How the system scales from 100 to 1M users, and where we bottleneck at each
step.

## Growth S-curve

| Tier | Users | Concurrency model | Bottleneck | Action |
|---|---|---|---|---|
| S       | 100 | SQLite→PG single box, 1 GPU | PG | cache, indexing |
| M     | 1k  | PG + Redis main DB | first GPU saturation | +1 vLLM, HPA |
| L     |10k 🔥 | PG+Redis+Qdrant, GPUs pool | queue burst | KEDA workers, embedding queue |
| XL   | 100k | partition PG, replica-join reads | write throughput | range partitions, VPC + read replica |
| XXL |1M | sharded KV + queue, SFU strings | global fanout | regional edge, Kafka ↔ RRate |

## 2. Real reasoning

- **API**: stateless; HPA 1→20 pods; JWT means no session affinity.
- **DB**: one PG → read replica for usage queries + pool; at 100k chats/day,
  `usage_records` & `messages` ranged-partition by month. Add now-means
  `partition by created_at` (we prep the schema for it in `docs/11`).
- **Retrieval**: Qdrant per collection; one collection, tenant filter — 
  corpus scale is bounded by index/RAM → move `on_disk_payload=true` + replica.
  Multi-collection shard when >1B vectors.
- **Streaming**: SSE is long-lived; proxy config sets timeouts; EventSource
  reconnects. Under Websocket-scale, swap in WebSockets for bidirectional edge
  (or keep SSE + backpressure — SSE is fine given one-direction flow; latency
  guard at 15min max by auto-closing after `done`).
- **Inference**: the GPU is the scarce resource. Per-GPU concurrency ~
  `batch=256/seq_len`; KEDA on vLLM queue; spot pools + warm standby.
- **Ingestion**: Celery `ingestion` queue scales via KEDA; embedding jobs for
  big uploads chunked; backpressure via `disable_queue`.

## 3. Capacity arithmetic (back-of-envelope)

Assume 1M daily users, 10% active/day, 4 conversations/user-month, ~8 agent
emulations per convo:
- API traffic: 40k conv/day ≈ 1.7 req/s chat + ~20 req/s total. Easy.
- Tokens/day: 40k conv × 5k tokens avg × ~8 agent calls ≈ 60M→ closer to
  250M tokens/month with streams. At a M token/$ (fine-tuned cost ≈ $0.08/1M),
  that's ~$20/day — well the ML budget is fine.
- Qdrant: 100GB corpus; 384d vectors = ~2.5GB; in-memory payload fine.
- PG: 1M conversations + ~10M rows messages; partitioned, heap ok.

## 4. Failure & scale priming checklist

- [ ] `/metrics` per pod removed; service-level SLOs.
- [ ] DB partitions + pgbouncer; HAPROXY at > 20k writers.
- [ ] KEDA autoscalers for workers.
- [ ] Rate shape for SSE vs long-poll.
- [ ] Presigned URL lifecycle for S3 (10min default).
- [ ] Per-workspace WAF/quota percentages.

> Numbers updated arch for realism; the interviews doc (`docs/17`) walks through
> "how would you handle 10×?" including the "buy vs build" for streaming
> at/composite, GPU bidding, and RDS→Aurora migration path.