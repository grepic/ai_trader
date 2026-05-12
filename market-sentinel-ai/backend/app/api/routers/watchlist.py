"""Watchlist management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.api.deps import DbSession
from app.models.core import WatchlistTicker
from app.schemas.core import WatchlistTickerCreate, WatchlistTickerOut

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=list[WatchlistTickerOut])
async def list_watchlist(db: DbSession):
    result = await db.execute(
        select(WatchlistTicker).order_by(WatchlistTicker.ticker)
    )
    return [WatchlistTickerOut.model_validate(w) for w in result.scalars().all()]


@router.post("", response_model=WatchlistTickerOut, status_code=201)
async def add_ticker(payload: WatchlistTickerCreate, db: DbSession):
    ticker = payload.ticker.upper()
    existing = await db.execute(
        select(WatchlistTicker).where(WatchlistTicker.ticker == ticker)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"{ticker} already in watchlist")

    wt = WatchlistTicker(
        ticker=ticker,
        name=payload.name,
        sector=payload.sector,
        max_position_usd=payload.max_position_usd,
        notes=payload.notes,
        is_active=True,
    )
    db.add(wt)
    await db.flush()
    return WatchlistTickerOut.model_validate(wt)


@router.delete("/{ticker}", status_code=204)
async def remove_ticker(ticker: str, db: DbSession):
    result = await db.execute(
        select(WatchlistTicker).where(WatchlistTicker.ticker == ticker.upper())
    )
    wt = result.scalar_one_or_none()
    if not wt:
        raise HTTPException(status_code=404, detail=f"{ticker} not in watchlist")
    await db.delete(wt)
