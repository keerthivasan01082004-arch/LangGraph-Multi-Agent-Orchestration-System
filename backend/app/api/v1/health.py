"""Health endpoints: liveness + readiness for LB/k8s probes."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter()


@router.get("/health/live")
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    # Deep-check dependencies so orchestrators can route traffic elsewhere.
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}