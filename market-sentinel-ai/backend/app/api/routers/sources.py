"""Source item endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.core import SourceItem, VerifiedEvent
from app.schemas.core import SourceItemOut, VerifiedEventOut

router = APIRouter(prefix="/api/sources", tags=["sources"])


@router.get("", response_model=list[SourceItemOut])
async def list_sources(db: DbSession, limit: int = 50, ticker: str | None = None):
    q = select(SourceItem).order_by(SourceItem.collected_at.desc()).limit(limit)
    if ticker:
        q = q.where(SourceItem.ticker_detected == ticker.upper())
    result = await db.execute(q)
    return [SourceItemOut.model_validate(s) for s in result.scalars().all()]


@router.get("/verified", response_model=list[VerifiedEventOut])
async def list_verified(db: DbSession, limit: int = 50, ticker: str | None = None):
    q = select(VerifiedEvent).order_by(VerifiedEvent.created_at.desc()).limit(limit)
    if ticker:
        q = q.where(VerifiedEvent.ticker == ticker.upper())
    result = await db.execute(q)
    return [VerifiedEventOut.model_validate(v) for v in result.scalars().all()]
