"""Trade endpoints."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.core import Order, TradeDecision
from app.schemas.core import OrderOut, TradeDecisionOut

router = APIRouter(prefix="/api/trades", tags=["trades"])


@router.get("", response_model=list[TradeDecisionOut])
async def list_trades(db: DbSession, limit: int = 50, executed_only: bool = False):
    q = select(TradeDecision).order_by(TradeDecision.created_at.desc()).limit(limit)
    if executed_only:
        q = q.where(TradeDecision.executed.is_(True))
    result = await db.execute(q)
    return [TradeDecisionOut.model_validate(t) for t in result.scalars().all()]


@router.get("/orders", response_model=list[OrderOut])
async def list_orders(db: DbSession, limit: int = 50):
    result = await db.execute(
        select(Order).order_by(Order.created_at.desc()).limit(limit)
    )
    return [OrderOut.model_validate(o) for o in result.scalars().all()]
