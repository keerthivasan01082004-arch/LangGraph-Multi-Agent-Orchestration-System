"""Versioned API router root."""

from fastapi import APIRouter

from app.api.v1 import auth, conversations, documents, health, usage # noqa: F401

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(documents.router, prefix="/workspaces/{workspace_id}/documents", tags=["documents"])
api_router.include_router(conversations.router, prefix="/workspaces/{workspace_id}/conversations", tags=["conversations"])
api_router.include_router(usage.router, tags=["usage"])  # usage.py carries its own /workspaces/{id} prefix