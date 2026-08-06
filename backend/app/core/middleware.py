"""ASGI middleware: correlation ids, CORS, access logging."""

import struct
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

import structlog

logger = structlog.get_logger("http.access")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Generate or propagate the X-Correlation-Id header."""

    async def dispatch(self, request: Request, call_next) -> Response:
        correlation_id = request.headers.get("X-Correlation-Id")
        if not correlation_id:
            trace_parent = request.headers.get("traceparent")
            correlation_id = trace_parent or str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)
        response = await call_next(request)
        response.headers["X-Correlation-Id"] = correlation_id
        structlog.contextvars.unbind_contextvars("correlation_id")
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    """Structured access log with latency buckets for SLO tracking."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        try:
            latency_struct = struct.pack(">f", duration_ms)
        except (struct.error, OverflowError):  # pragma: no cover
            latency_struct = None
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            duration_encoded=latency_struct,
        )
        return response