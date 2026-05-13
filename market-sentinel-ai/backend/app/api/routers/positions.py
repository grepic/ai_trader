"""Position endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.api.deps import Broker, DbSession
from app.models.core import PositionSnapshot, PortfolioSnapshot
from app.schemas.core import PositionSnapshotOut, PortfolioSnapshotOut

router = APIRouter(prefix="/api/positions", tags=["positions"])


@router.get("", response_model=list[PositionSnapshotOut])
async def get_positions(broker: Broker, db: DbSession):
    """Return current open positions from broker and snapshot to DB."""
    positions = await broker.get_positions()
    now = datetime.now(timezone.utc)
    result = []

    for pos in positions:
        snap = PositionSnapshot(
            ticker=pos.ticker,
            quantity=pos.quantity,
            avg_entry_price=pos.avg_entry_price,
            current_price=pos.current_price,
            market_value=pos.market_value,
            unrealized_pl=pos.unrealized_pl,
            unrealized_pl_pct=pos.unrealized_pl_pct,
            paper_mode=broker.is_paper,
            snapshot_at=now,
        )
        db.add(snap)
        result.append(PositionSnapshotOut.model_validate(snap))

    await db.flush()
    return result


@router.get("/portfolio", response_model=PortfolioSnapshotOut)
async def get_portfolio(broker: Broker, db: DbSession):
    """Return current portfolio snapshot from broker."""
    account = await broker.get_account()
    positions = await broker.get_positions()
    now = datetime.now(timezone.utc)

    positions_value = sum(p.market_value for p in positions)
    unrealized_pl = sum(p.unrealized_pl for p in positions)

    snap = PortfolioSnapshot(
        account_value=account.equity,
        cash_balance=account.cash,
        positions_value=positions_value,
        unrealized_pl=unrealized_pl,
        realized_pl_today=0.0,
        daily_pl=account.equity - account.last_equity,
        trades_today=0,
        open_positions=len(positions),
        paper_mode=broker.is_paper,
        snapshot_at=now,
    )
    db.add(snap)
    await db.flush()
    return PortfolioSnapshotOut.model_validate(snap)


@router.post("/{ticker}/close")
async def close_position(ticker: str, broker: Broker):
    """Close (liquidate) a specific open position via the broker."""
    ticker = ticker.upper()
    positions = await broker.get_positions()
    open_tickers = {p.ticker for p in positions}

    if ticker not in open_tickers:
        raise HTTPException(status_code=404, detail=f"No open position for {ticker}")

    order = await broker.close_position(ticker)
    if not order:
        raise HTTPException(status_code=500, detail=f"Broker failed to close {ticker}")

    return {
        "status": "closed",
        "ticker": ticker,
        "broker_order_id": order.broker_order_id,
        "filled_price": order.filled_price,
    }
