"""Unified API error framework.

Every failure surfaces as a typed ApiError with:
  - a stable machine-readable `code`
  - an HTTP status
  - a human `message`
  - optional `details` for validation context

FastAPI converts these into the documented JSON error envelope.
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import FastAPI, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    """Base class for all Conductor API errors."""

    def __init__(
        self,
        code: str,
        message: str,
        http_status: int = status.HTTP_400_BAD_REQUEST,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details or []

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {"error": {"code": self.code, "message": self.message}}
        if self.details:
            body["error"]["details"] = self.details
        return body


class NotFoundError(APIError):
    def __init__(self, resource: str, resource_id: str | int) -> None:
        super().__init__(
            code="not_found",
            message=f"{resource} {resource_id} not found",
            http_status=status.HTTP_404_NOT_FOUND,
        )


class AuthorizationError(APIError):
    def __init__(self, message: str = "Not authorized") -> None:
        super().__init__(
            code="unauthorized",
            message=message,
            http_status=status.HTTP_401_UNAUTHORIZED,
        )


class PermissionDeniedError(APIError):
    def __init__(self, message: str = "Forbidden") -> None:
        super().__init__(
            code="forbidden",
            message=message,
            http_status=status.HTTP_403_FORBIDDEN,
        )


class ConflictError(APIError):
    def __init__(self, message: str) -> None:
        super().__init__(code="conflict", message=message, http_status=status.HTTP_409_CONFLICT)


class RateLimitError(APIError):
    def __init__(self, message: str = "Rate limit exceeded") -> None:
        super().__init__(code="rate_limited", message=message, http_status=status.HTTP_429_TOO_MANY_REQUESTS)


class UpstreamError(APIError):
    def __init__(self, message: str = "Upstream service unavailable") -> None:
        super().__init__(
            code="upstream_unavailable",
            message=message,
            http_status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(APIError)
    async def api_error_handler(_, exc: APIError) -> JSONResponse:
        return JSONResponse(status_code=exc.http_status, content=exc.to_dict())

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_, exc: StarletteHTTPException) -> JSONResponse:
        # Re-map to the stable envelope so clients only parse one shape.
        payload: dict[str, Any] = {"error": {"code": "http_error", "message": str(exc.detail)}}
        if exc.status_code == status.HTTP_401_UNAUTHORIZED:
            payload["error"]["code"] = "unauthorized"
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            payload["error"]["code"] = "forbidden"
        elif exc.status_code == status.HTTP_404_NOT_FOUND:
            payload["error"]["code"] = "not_found"
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
        details = []
        for err in exc.errors():
            details.append({"field": ".".join(str(i) for i in err.get("loc", [])), "msg": err.get("msg")})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": {"code": "validation_error", "message": "Request validation failed", "details": details}},
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_, exc: Exception) -> JSONResponse:
        logger = structlog.get_logger("error")
        logger.exception("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )