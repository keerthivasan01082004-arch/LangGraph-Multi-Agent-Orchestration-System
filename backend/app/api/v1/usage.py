"""Usage and cost telemetry endpoints for admins and end-users."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import PermissionDeniedError
from app.db.models import UsageRecord, User, WorkspaceMember
from app.db.session import get_db

router = APIRouter(prefix="/workspaces/{workspace_id}")


@router.get("/usage/summary")
def usage_summary(
    workspace_id: str,
    from_date: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, object]:
    membership = (
        db.query(WorkspaceMember).filter(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user.id).first()
    )
    if membership is None:
        raise PermissionDeniedError("workspace not accessible")
    row = (
        db.query(
            func.sum(UsageRecord.prompt_tokens),
            func.sum(UsageRecord.completion_tokens),
            func.sum(UsageRecord.cost_usd),
            func.count(UsageRecord.id),
        )
        .filter(UsageRecord.workspace_id == workspace_id, func.date(UsageRecord.created_at) >= from_date)
        .one()
    )
    return {
        "workspace_id": workspace_id,
        "prompt_tokens": int(row[0] or 0),
        "completion_tokens": int(row[1] or 0),
        "cost_usd": round(float(row[2] or 0), 4),
        "requests": int(row[3] or 0),
    }