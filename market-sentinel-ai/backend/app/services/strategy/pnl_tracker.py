"""Realized P&L tracker — calculates trade-by-trade profit/loss from order history."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import Order, TradeDecision

logger = logging.getLogger(__name__)


class PnLTracker:
    """
    Computes realized P&L by pairing buy/sell orders per ticker (FIFO basis).
    Persists nothing — recalculates from order history each time.
    """

    async def get_daily_realized_pnl(self, db: AsyncSession, report_date: date | None = None) -> float:
        """Sum of realized P&L for all closed positions on a given date."""
        target_date = report_date or date.today()
        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = datetime.combine(target_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        result = await db.execute(
            select(Order)
            .where(
                Order.status == "filled",
                Order.side == "sell",
                Order.filled_at >= day_start,
                Order.filled_at <= day_end,
            )
            .order_by(Order.filled_at)
        )
        sell_orders = result.scalars().all()

        total_pnl = 0.0
        for sell in sell_orders:
            # Find the corresponding buy order(s) for this ticker
            buy_result = await db.execute(
                select(Order)
                .where(
                    Order.ticker == sell.ticker,
                    Order.side == "buy",
                    Order.status == "filled",
                    Order.filled_at < sell.filled_at,
                )
                .order_by(Order.filled_at)
                .limit(1)
            )
            buy = buy_result.scalar_one_or_none()
            if buy and buy.filled_price and sell.filled_price:
                pnl = (sell.filled_price - buy.filled_price) * (sell.filled_quantity or sell.quantity)
                total_pnl += pnl

        return round(total_pnl, 2)

    async def get_trade_stats_today(self, db: AsyncSession) -> dict[str, Any]:
        """Aggregate win/loss stats for today's executed trades."""
        today = date.today()
        day_start = datetime.combine(today, datetime.min.time()).replace(tzinfo=timezone.utc)

        result = await db.execute(
            select(TradeDecision)
            .where(
                TradeDecision.executed.is_(True),
                TradeDecision.created_at >= day_start,
            )
        )
        decisions = result.scalars().all()

        wins = 0
        losses = 0
        best_ticker = None
        best_pl = 0.0
        worst_ticker = None
        worst_pl = 0.0

        for d in decisions:
            if d.target_price and d.stop_loss_price and d.quantity:
                # Rough P&L estimate for open positions
                est_pl = (d.target_price - (d.stop_loss_price * 1.01)) * d.quantity
                if est_pl > 0:
                    wins += 1
                    if best_ticker is None or est_pl > best_pl:
                        best_ticker = d.ticker
                        best_pl = est_pl
                else:
                    losses += 1
                    if worst_ticker is None or est_pl < worst_pl:
                        worst_ticker = d.ticker
                        worst_pl = est_pl

        return {
            "total_trades": len(decisions),
            "winning_trades": wins,
            "losing_trades": losses,
            "best_trade_ticker": best_ticker,
            "best_trade_pl": round(best_pl, 2) if best_ticker else None,
            "worst_trade_ticker": worst_ticker,
            "worst_trade_pl": round(worst_pl, 2) if worst_ticker else None,
        }
