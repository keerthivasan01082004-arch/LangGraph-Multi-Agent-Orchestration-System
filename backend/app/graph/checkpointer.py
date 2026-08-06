"""Checkpointing and long-term memory backends.

Short-term memory (per-thread conversation state) uses the LangGraph Postgres
checkpointer — durable, resumable, and consistent with the API database.

Long-term memory (cross-conversation facts per user/workspace) uses the
LangGraph Postgres store. Design details in docs/08-memory-architecture.md.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_graph_checkpointer():
    from langgraph.checkpoint.postgres import PostgresSaver

    settings = get_settings()
    saver = PostgresSaver.from_conn_string(settings.database_url)
    # Idempotent: creates checkpoint tables on first run.
    saver.setup()
    return saver


@lru_cache
def get_store():
    from langgraph.store.postgres import PostgresStore

    settings = get_settings()
    store = PostgresStore.from_conn_string(settings.database_url)
    store.setup()
    return store