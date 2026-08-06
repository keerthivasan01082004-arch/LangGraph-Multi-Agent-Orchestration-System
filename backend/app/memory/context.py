"""Memory architecture helpers.

Layers (full design in docs/08-memory-architecture.md):
  short-term   → LangGraph thread checkpoint (per thread_id)
  long-term    → per-user store (PostgresStore) via app.memory.store
  conversation → message list on the checkpoint
  vector       → Qdrant workspace knowledge base
  summarization→ token-budget projection below
"""

from __future__ import annotations

from typing import Any

from app.ingestion.chunkers import token_count

MAX_CONTEXT_TOKENS = 8192


def summarize_messages(messages: list[dict[str, Any]], max_tokens: int = MAX_CONTEXT_TOKENS) -> list[dict[str, Any]]:
    """Project recent messages into a token budget, prepending a summary stub."""
    total = sum(token_count(m.get("content", "")) for m in messages)
    if total <= max_tokens:
        return messages

    summary_line = {"role": "system", "content": "[summarized earlier conversation]"}
    budget_left = max_tokens - token_count(summary_line["content"])
    kept: list[dict[str, Any]] = []
    used = 0
    for message in reversed(messages):
        cost = token_count(message.get("content", ""))
        if used + cost > budget_left:
            break
        kept.insert(0, message)
        used += cost
    return [summary_line, *kept]


def evict_old_messages(messages: list[dict[str, Any]], keep: int = 12) -> list[dict[str, Any]]:
    return messages[-keep:] if len(messages) > keep else messages


def topic_of(messages: list[dict[str, Any]]) -> str:
    """Cheap topic hint from the first user message (used as store namespace key)."""
    for message in messages:
        if message.get("role") == "user":
            return message.get("content", "general")[:120]
    return "general"