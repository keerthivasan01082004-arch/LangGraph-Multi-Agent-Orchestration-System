"""Memory subsystem.

- Short-term: per-thread conversation carried by the LangGraph checkpoint
  (Postgres). Managed automatically by the graph.
- Long-term: langgraph.store key-value memory for cross-conversation facts,
  namespaced by workspace → user.
- Summarization + eviction: helpers used by the compaction step before each
  agent node.

docs/08-memory-architecture.md has the full design.
"""

from __future__ import annotations

from app.graph.checkpointer import get_store

NAMESPACE_FACTS = ("conductor", "facts")
TOKEN_BUDGET_MESSAGES = 20_000  # rough prompt-token ceiling for the conversation slab


def save_fact(workspace_id: str, user_id: str, fact: str, importance: float = 0.5) -> None:
    """Persist a durable fact to the long-term store."""
    store = get_store()
    store.put(
        NAMESPACE_FACTS + (workspace_id, user_id),
        key=fact[:80],
        value={"fact": fact, "importance": importance, "created_at": _now_iso()},
    )


def recall_facts(workspace_id: str, user_id: str, query: str, limit: int = 10) -> list[str]:
    """Semantically search durable facts for the given user/workspace."""
    store = get_store()
    try:
        items = store.search(NAMESPACE_FACTS + (workspace_id, user_id), query=query, limit=limit)
    except Exception:
        items = store.list(NAMESPACE_FACTS + (workspace_id, user_id), limit=limit)
    return [i.value.get("fact", "") for i in items]


def should_compact(messages_token_estimate: int) -> bool:
    return messages_token_estimate > TOKEN_BUDGET_MESSAGES


def summarize_thread(history: list[dict[str, object]]) -> str:
    """Compress a thread into a working summary for later turns.

    The scaffold uses deterministic extraction; production swaps in the
    system summarizer prompt (docs/08-memory-architecture.md) so the summary
    keeps reasoning context, not just raw text.
    """
    user_turns = [m for m in history if m.get("role") == "user"]
    snippets = " ".join(str(m.get("content", ""))[:200] for m in user_turns[-5:])
    return f"[Summary of {len(user_turns)} user turns] {snippets}"


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()