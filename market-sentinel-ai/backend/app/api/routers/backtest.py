"""Backtesting endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.core import BacktestRequest, BacktestResult
from app.services.backtesting.engine import BacktestEngine

router = APIRouter(prefix="/api/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResult)
async def run_backtest(request: BacktestRequest):
    engine = BacktestEngine()
    result = engine.run(
        tickers=request.tickers,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        strategy=request.strategy,
    )
    return BacktestResult(**result)
