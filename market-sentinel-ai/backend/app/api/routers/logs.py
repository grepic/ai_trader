"""System logs endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.core import SystemLog
from app.schemas.core import SystemLogOut

router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=list[SystemLogOut])
async def list_logs(
    db: DbSession,
    limit: int = 100,
    level: str | None = None,
    component: str | None = None,
    ticker: str | None = None,
):
    q = select(SystemLog).order_by(SystemLog.created_at.desc()).limit(limit)
    if level:
        q = q.where(SystemLog.level == level.upper())
    if component:
        q = q.where(SystemLog.component == component)
    if ticker:
        q = q.where(SystemLog.ticker == ticker.upper())
    result = await db.execute(q)
    return [SystemLogOut.model_validate(r) for r in result.scalars().all()]
