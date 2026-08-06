"""Cost accounting: per-agent usage rows + workspace daily aggregates.

Feeds the /usage endpoints, billing, and the cost-optimization feedback loop
(docs/16-cost-optimization.md). Token prices come from app/models/gateway.py.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.db.models import Conversation, UsageRecord

logger = structlog.get_logger("cost")


def persist_usage(db: Any, conversation: Conversation, usage: dict[str, Any]) -> None:
    """Write one UsageRecord per agent call."""
    try:
        db.add(
            UsageRecord(
                workspace_id=conversation.workspace_id,
                user_id=conversation.created_by,
                conversation_id=conversation.id,
                model_id=usage.get("model", "unknown"),
                agent=usage.get("agent", "unknown"),
                prompt_tokens=usage.get("input_tokens", 0),
                completion_tokens=usage.get("output_tokens", 0),
                total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
                cost_usd=float(usage.get("cost_usd", 0.0)),
                cached=bool(usage.get("cached", False)),
            )
        )
        db.commit()
    except Exception:
        logger.exception("usage_persist_failed")