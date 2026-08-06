"""Prometheus instrumentation.

Exposing key SLO surface for the Grafana dashboards (docs/14-monitoring.md).
Endpoints counter is maintained by middleware; agent/cost metrics are
incremented by the orchestrator. Exposed at GET /metrics.
"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by method and path",
    ["method", "path", "status"],
)

request_duration_seconds = Histogram(
    "request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60),
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM call latency by agent",
    ["agent"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 60, 120),
)

conductor_cost_usd_total = Counter(
    "conductor_cost_usd_total",
    "Accumulated estimated inference cost in USD",
    ["model"],
)

conductor_tokens_total = Counter(
    "conductor_tokens_total",
    "Tokens processed by agent",
    ["agent"],
)

conductor_agent_rejections_total = Counter(
    "conductor_agent_rejections_total",
    "Critic rejections (retry loop iterations)",
)

gpu_saturation = Gauge("vllm_gpu_utilization", "Average GPU utilization reported by vLLM")


def observe_request(method: str, path: str, status_code: int, duration_ms: float) -> None:
    http_requests_total.labels(method=method, path=path, status=status_code).inc()
    request_duration_seconds.labels(method=method, path=path).observe(duration_ms / 1000.0)


def observe_llm(*, agent: str, duration_ms: float) -> None:
    llm_latency_seconds.labels(agent).observe(duration_ms / 1000.0)


def record_usage(*, agent: str, tokens: int, cost_usd: float, model: str) -> None:
    conductor_tokens_total.labels(agent).inc(tokens)
    conductor_cost_usd_total.labels(model).inc(cost_usd)


def record_rejection() -> None:
    conductor_agent_rejections_total.inc()