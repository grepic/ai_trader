"""Risk control endpoints — pause, resume, emergency stop."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import Broker, Risk
from app.api.rate_limit import bot_control_limiter
from app.config import get_settings
from app.schemas.core import RiskStatusOut

router = APIRouter(prefix="/api", tags=["risk"])


@router.get("/risk/status", response_model=RiskStatusOut)
async def get_risk_status(risk: Risk, broker: Broker):
    status = risk.get_status()
    positions = await broker.get_positions()
    market_open = await broker.is_market_open()
    settings = get_settings()

    warnings: list[str] = []
    if status["daily_loss_pct"] > 80:
        warnings.append(f"Daily loss at {status['daily_loss_pct']:.0f}% of limit")
    if not market_open:
        warnings.append("Market is currently closed")
    if status["emergency_stopped"]:
        warnings.append("EMERGENCY STOP is active")

    return RiskStatusOut(
        bot_running=status["bot_running"],
        paper_mode=status["paper_mode"],
        emergency_stopped=status["emergency_stopped"],
        daily_loss_usd=status["daily_loss_usd"],
        max_daily_loss_usd=status["max_daily_loss_usd"],
        daily_loss_pct=status["daily_loss_pct"],
        open_positions=len(positions),
        max_open_positions=settings.max_open_positions,
        trades_today=status["trades_today"],
        trading_allowed=status["bot_running"] and market_open,
        market_open=market_open,
        risk_warnings=warnings,
    )


@router.post("/bot/pause", dependencies=[Depends(bot_control_limiter)])
async def pause_bot(risk: Risk):
    risk.pause()
    return {"status": "paused", "message": "Bot has been manually paused. No new trades will execute."}


@router.post("/bot/resume", dependencies=[Depends(bot_control_limiter)])
async def resume_bot(risk: Risk):
    if risk.get_status()["emergency_stopped"]:
        raise HTTPException(
            status_code=400,
            detail="Cannot resume: emergency stop is active. Contact admin to reset.",
        )
    risk.resume()
    return {"status": "running", "message": "Bot resumed."}


@router.post("/bot/emergency-stop", dependencies=[Depends(bot_control_limiter)])
async def emergency_stop(risk: Risk, broker: Broker):
    risk.emergency_stop()
    # Close all positions on emergency stop
    positions = await broker.get_positions()
    closed = []
    for pos in positions:
        order = await broker.close_position(pos.ticker)
        if order:
            closed.append(pos.ticker)

    return {
        "status": "emergency_stopped",
        "message": "Emergency stop activated. All positions closed.",
        "positions_closed": closed,
    }
