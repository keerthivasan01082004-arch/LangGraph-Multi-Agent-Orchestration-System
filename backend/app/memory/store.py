"""Long-term memory facade over the LangGraph Store.

Namespaces: (user_id, "preferences"), (user_id, "facts"), (user_id, "topics").
Persisted via PostgresStore in production; caller supplies the store instance
created by app/graph/checkpointer.get_store().
"""

from __future__ import annotations

from typing import Any


def remember(store: Any, user_id: str, namespace: str, key: str, value: dict[str, Any]) -> None:
    if store is None:
        return
    store.put((user_id, namespace), key, value={"value": value})


def recall(store: Any, user_id: str, namespace: str, key: str) -> dict[str, Any] | None:
    if store is None:
        return None
    item = store.get((user_id, namespace), key)
    if item is None:
        return None
    return (item.value or {}).get("value", {})


def list_memories(store: Any, user_id: str, namespace: str) -> list[dict[str, Any]]:
    if store is None:
        return []
    return [item.value for item in store.search((user_id, namespace))]