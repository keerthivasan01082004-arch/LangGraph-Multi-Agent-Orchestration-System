"""Checkpointer for thread history: LangGraph PostgresSaver.

Persists every step checkpoint per thread_id → conversation resume, fault
tolerance, and human-in-the-loop interrupts survive process restarts.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.config import get_settings


def get_checkpointer() -> Any | None:
    """Build a PostgresSaver lazily.

    Returns None when the database is unreachable (scaffold/CI mode) so the
    app still boots. Production wiring guarantees the checkpointer is present.
    """
    from langgraph.checkpoint.postgres import PostgresSaver

    settings = get_settings()
    try:
        saver = PostgresSaver.from_conn_string(settings.database_url)
        saver.setup()
        return saver
    except Exception:
        return None


def get_store() -> Any | None:
    """Long-term memory store (Postgres-backed in production)."""
    from langgraph.store.postgres import PostgresStore

    settings = get_settings()
    try:
        store = PostgresStore.from_conn_string(settings.database_url)
        store.setup()
        return store
    except Exception:
        return None