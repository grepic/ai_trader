"""Simple backtesting engine — replays historical signals against mock price data."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any


@dataclass
class BacktestTrade:
    ticker: str
    entry_date: str
    exit_date: str
    entry_price: float
    exit_price: float
    quantity: float
    side: str  # buy|short
    pnl: float
    pnl_pct: float
    signal_confidence: float


class BacktestEngine:
    """
    Simplified event-driven backtester.

    Uses synthetic price walks if no real data is available (for demo/dev).
    In production, replace _get_price_series with real OHLCV data from Alpaca or another source.
    """

    def run(
        self,
        tickers: list[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 10_000.0,
        strategy: str = "news_momentum",
    ) -> dict[str, Any]:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
        days = (end - start).days
        if days < 1:
            raise ValueError("end_date must be after start_date")

        capital = initial_capital
        equity_curve: list[dict[str, Any]] = [{"date": start_date, "equity": capital}]
        trades: list[BacktestTrade] = []
        max_equity = capital
        max_drawdown = 0.0

        # Simulate for each ticker independently, then combine
        for ticker in tickers:
            prices = self._get_price_series(ticker, start, days)
            ticker_trades = self._simulate_strategy(
                ticker=ticker,
                prices=prices,
                start=start,
                capital=capital / len(tickers),
                strategy=strategy,
            )
            trades.extend(ticker_trades)

        # Rebuild equity curve from all trades
        capital = initial_capital
        trade_by_date: dict[str, float] = {}
        for t in trades:
            trade_by_date[t.exit_date] = trade_by_date.get(t.exit_date, 0) + t.pnl

        current = start
        while current <= end:
            ds = current.isoformat()
            capital += trade_by_date.get(ds, 0)
            equity_curve.append({"date": ds, "equity": round(capital, 2)})
            if capital > max_equity:
                max_equity = capital
            drawdown = (max_equity - capital) / max_equity * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
            current += timedelta(days=1)

        # Metrics
        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]
        total_return = (capital - initial_capital) / initial_capital * 100
        win_rate = len(wins) / len(trades) * 100 if trades else 0
        avg_win = sum(t.pnl for t in wins) / len(wins) if wins else 0
        avg_loss = sum(t.pnl for t in losses) / len(losses) if losses else 0

        # Simplified Sharpe (daily returns)
        daily_pnls = list(trade_by_date.values())
        if len(daily_pnls) > 1:
            mean_r = sum(daily_pnls) / len(daily_pnls)
            variance = sum((r - mean_r) ** 2 for r in daily_pnls) / len(daily_pnls)
            std_r = math.sqrt(variance) if variance > 0 else 1e-9
            sharpe = (mean_r / std_r) * math.sqrt(252)
        else:
            sharpe = 0.0

        best = max(trades, key=lambda t: t.pnl, default=None)
        worst = min(trades, key=lambda t: t.pnl, default=None)

        return {
            "strategy": strategy,
            "tickers": tickers,
            "start_date": start_date,
            "end_date": end_date,
            "initial_capital": initial_capital,
            "final_capital": round(capital, 2),
            "total_return_pct": round(total_return, 2),
            "win_rate_pct": round(win_rate, 1),
            "max_drawdown_pct": round(max_drawdown, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss, 2),
            "sharpe_ratio": round(sharpe, 2),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "best_trade": {
                "ticker": best.ticker,
                "pnl": round(best.pnl, 2),
                "date": best.exit_date,
            } if best else None,
            "worst_trade": {
                "ticker": worst.ticker,
                "pnl": round(worst.pnl, 2),
                "date": worst.exit_date,
            } if worst else None,
            "equity_curve": equity_curve[-100:],  # Last 100 points for charting
        }

    def _get_price_series(self, ticker: str, start: date, days: int) -> list[float]:
        """
        Generate a synthetic price walk for demo purposes.
        Replace with real OHLCV data (Alpaca, Yahoo, etc.) in production.
        """
        seed_prices = {
            "AAPL": 170.0, "TSLA": 200.0, "NVDA": 450.0,
            "MSFT": 400.0, "GOOGL": 150.0, "AMZN": 180.0, "SPY": 490.0,
        }
        base = seed_prices.get(ticker.upper(), 100.0)
        rng = random.Random(hash(ticker + str(start)))
        prices = [base]
        for _ in range(days):
            change = rng.gauss(0.0005, 0.018)  # ~0.05% drift, 1.8% daily vol
            prices.append(round(prices[-1] * (1 + change), 2))
        return prices

    def _simulate_strategy(
        self,
        ticker: str,
        prices: list[float],
        start: date,
        capital: float,
        strategy: str,
    ) -> list[BacktestTrade]:
        """Simulate a simple momentum strategy on synthetic prices."""
        trades: list[BacktestTrade] = []
        in_position = False
        entry_price = 0.0
        entry_date = ""
        quantity = 0.0
        rng = random.Random(hash(ticker + strategy))

        for i, price in enumerate(prices[1:], 1):
            current_date = (start + timedelta(days=i)).isoformat()

            if not in_position:
                # Enter on simulated signal (30% chance per day for demo)
                signal_confidence = rng.uniform(50, 100)
                if signal_confidence >= 75 and rng.random() < 0.15:
                    max_spend = min(capital * 0.2, capital)
                    if max_spend >= price:
                        quantity = max_spend / price
                        entry_price = price
                        entry_date = current_date
                        in_position = True
            else:
                # Exit on take-profit (5%), stop-loss (3%), or random (10%)
                change_pct = (price - entry_price) / entry_price
                if change_pct >= 0.05 or change_pct <= -0.03 or rng.random() < 0.10:
                    pnl = quantity * (price - entry_price)
                    trades.append(BacktestTrade(
                        ticker=ticker,
                        entry_date=entry_date,
                        exit_date=current_date,
                        entry_price=entry_price,
                        exit_price=price,
                        quantity=quantity,
                        side="buy",
                        pnl=round(pnl, 2),
                        pnl_pct=round(change_pct * 100, 2),
                        signal_confidence=75.0,
                    ))
                    capital += pnl
                    in_position = False

        # Close any open position at end
        if in_position and prices:
            price = prices[-1]
            pnl = quantity * (price - entry_price)
            trades.append(BacktestTrade(
                ticker=ticker,
                entry_date=entry_date,
                exit_date=(start + timedelta(days=len(prices) - 1)).isoformat(),
                entry_price=entry_price,
                exit_price=price,
                quantity=quantity,
                side="buy",
                pnl=round(pnl, 2),
                pnl_pct=round((price - entry_price) / entry_price * 100, 2),
                signal_confidence=75.0,
            ))

        return trades
