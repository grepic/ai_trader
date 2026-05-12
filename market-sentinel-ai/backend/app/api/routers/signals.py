"""Signal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.core import AISignal
from app.schemas.core import AISignalOut

router = APIRouter(prefix="/api/signals", tags=["signals"])


@router.get("", response_model=list[AISignalOut])
async def list_signals(db: DbSession, limit: int = 50, ticker: str | None = None):
    q = select(AISignal).order_by(AISignal.created_at.desc()).limit(limit)
    if ticker:
        q = q.where(AISignal.ticker == ticker.upper())
    result = await db.execute(q)
    return [AISignalOut.model_validate(s) for s in result.scalars().all()]


@router.get("/{signal_id}", response_model=AISignalOut)
async def get_signal(signal_id: str, db: DbSession):
    result = await db.execute(select(AISignal).where(AISignal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return AISignalOut.model_validate(signal)
