"""FastAPI application factory + lifespan.

Composes middleware, error handlers, routers, and telemetry in a single place
so tests can build isolated app instances.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.api.router import api_router
from app.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import AccessLogMiddleware, CorrelationIdMiddleware


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging(get_settings())
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Conductor API",
        description="Multi-agent orchestration platform — LangGraph, Mistral-7B, FastAPI.",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(CorrelationIdMiddleware)

    install_error_handlers(app)

    app.include_router(api_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()