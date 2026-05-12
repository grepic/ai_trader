"""Overview and health endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select, func

from app.api.deps import DbSession, Broker, Risk
from app.models.core import AISignal, PortfolioSnapshot, TradeDecision
from app.schemas.core import AISignalOut, BotStatusOut, PortfolioSnapshotOut, RiskStatusOut, TradeDecisionOut

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/api/overview")
async def get_overview(db: DbSession, broker: Broker, risk: Risk):
    account = await broker.get_account()
    positions = await broker.get_positions()
    market_open = await broker.is_market_open()
    risk_status = risk.get_status()

    # Latest portfolio snapshot
    snap_result = await db.execute(
        select(PortfolioSnapshot).order_by(PortfolioSnapshot.snapshot_at.desc()).limit(1)
    )
    snap = snap_result.scalar_one_or_none()

    # Recent signals (last 10)
    sig_result = await db.execute(
        select(AISignal).order_by(AISignal.created_at.desc()).limit(10)
    )
    signals = [AISignalOut.model_validate(s) for s in sig_result.scalars().all()]

    # Recent trades (last 10)
    trade_result = await db.execute(
        select(TradeDecision)
        .where(TradeDecision.executed.is_(True))
        .order_by(TradeDecision.created_at.desc())
        .limit(10)
    )
    trades = [TradeDecisionOut.model_validate(t) for t in trade_result.scalars().all()]

    # Count today's signals
    from datetime import date
    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    count_result = await db.execute(
        select(func.count(AISignal.id)).where(AISignal.created_at >= today_start)
    )
    signals_today = count_result.scalar() or 0

    bot_status = BotStatusOut(
        running=risk_status["bot_running"],
        paper_mode=risk_status["paper_mode"],
        emergency_stopped=risk_status["emergency_stopped"],
        market_open=market_open,
        account_value=account.equity,
        cash_balance=account.cash,
        daily_pl=snap.daily_pl if snap else 0.0,
        open_positions=len(positions),
        trades_today=risk_status["trades_today"],
        signals_today=signals_today,
        last_updated=datetime.now(timezone.utc),
    )

    risk_out = RiskStatusOut(
        bot_running=risk_status["bot_running"],
        paper_mode=risk_status["paper_mode"],
        emergency_stopped=risk_status["emergency_stopped"],
        daily_loss_usd=risk_status["daily_loss_usd"],
        max_daily_loss_usd=risk_status["max_daily_loss_usd"],
        daily_loss_pct=risk_status["daily_loss_pct"],
        open_positions=len(positions),
        max_open_positions=5,
        trades_today=risk_status["trades_today"],
        trading_allowed=risk_status["bot_running"] and market_open,
        market_open=market_open,
        risk_warnings=[],
    )

    return {
        "bot_status": bot_status,
        "portfolio": PortfolioSnapshotOut.model_validate(snap) if snap else None,
        "recent_signals": signals,
        "recent_trades": trades,
        "risk_status": risk_out,
    }
