"""Risk Management Engine — all trading decisions must pass through this."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.config import get_settings
from app.schemas.core import AISignalOut

if TYPE_CHECKING:
    from app.services.broker.base import BrokerClient

logger = logging.getLogger(__name__)


@dataclass
class RiskCheckResult:
    passed: bool
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggested_quantity: float | None = None
    suggested_stop_loss: float | None = None
    suggested_take_profit: float | None = None

    @property
    def notes(self) -> str:
        return "; ".join(self.reasons + self.warnings)


class RiskEngine:
    """
    Deterministic risk gate that all trade decisions must pass.

    State is in-memory and reset at instantiation. In production, persist
    daily_loss and trade counts to DB for crash-safety.
    """

    def __init__(self, broker: "BrokerClient | None" = None):
        self._settings = get_settings()
        self._broker = broker
        self._bot_running: bool = True
        self._emergency_stopped: bool = False
        self._manual_paused: bool = False
        self._daily_loss_usd: float = 0.0
        self._trades_today: int = 0
        self._trades_per_ticker_today: dict[str, int] = {}
        self._last_trade_date: date = date.today()
        self._cooldown_until: dict[str, datetime] = {}

    # ------------------------------------------------------------------
    # Bot control
    # ------------------------------------------------------------------

    def pause(self) -> None:
        self._manual_paused = True
        logger.warning("Bot manually PAUSED")

    def resume(self) -> None:
        if self._emergency_stopped:
            logger.error("Cannot resume — emergency stop is active")
            return
        self._manual_paused = False
        logger.info("Bot RESUMED")

    def emergency_stop(self) -> None:
        self._emergency_stopped = True
        self._bot_running = False
        logger.critical("EMERGENCY STOP activated")

    def reset_emergency_stop(self) -> None:
        """Only call this after human review."""
        self._emergency_stopped = False
        self._bot_running = True
        logger.warning("Emergency stop RESET — trading re-enabled")

    # ------------------------------------------------------------------
    # Daily state management
    # ------------------------------------------------------------------

    def _maybe_reset_daily_counters(self) -> None:
        today = date.today()
        if today != self._last_trade_date:
            self._daily_loss_usd = 0.0
            self._trades_today = 0
            self._trades_per_ticker_today = {}
            self._last_trade_date = today

    def record_trade_result(self, ticker: str, pnl: float) -> None:
        """Call after a trade closes to update daily tracking."""
        self._maybe_reset_daily_counters()
        if pnl < 0:
            self._daily_loss_usd += abs(pnl)
        self._trades_today += 1
        self._trades_per_ticker_today[ticker] = (
            self._trades_per_ticker_today.get(ticker, 0) + 1
        )

    def set_cooldown(self, ticker: str, seconds: int = 300) -> None:
        """Prevent trading a ticker for `seconds` after a trade."""
        from datetime import timedelta
        self._cooldown_until[ticker] = datetime.now(timezone.utc) + timedelta(seconds=seconds)

    # ------------------------------------------------------------------
    # Main risk check
    # ------------------------------------------------------------------

    async def check_trade(
        self,
        signal: AISignalOut,
        current_price: float,
        account_cash: float,
        open_position_count: int,
        market_open: bool,
    ) -> RiskCheckResult:
        """Run all risk checks. Returns RiskCheckResult with passed=True only if safe to trade."""
        self._maybe_reset_daily_counters()
        s = self._settings
        result = RiskCheckResult(passed=True)

        # 1. Emergency stop / pause
        if self._emergency_stopped:
            result.passed = False
            result.reasons.append("Emergency stop is active")
            return result

        if self._manual_paused:
            result.passed = False
            result.reasons.append("Bot is manually paused")
            return result

        # 2. Paper mode safety
        if not s.is_paper_mode and not s.real_trading_enabled:
            result.passed = False
            result.reasons.append("Real trading not explicitly enabled")
            return result

        # 3. Market must be open
        if not market_open:
            result.passed = False
            result.reasons.append("Market is closed")
            return result

        # 4. Ticker in watchlist check is done upstream; we trust the signal here

        # 5. Confidence threshold
        if signal.confidence < s.min_confidence_to_trade:
            result.passed = False
            result.reasons.append(
                f"Signal confidence {signal.confidence:.1f} < threshold {s.min_confidence_to_trade}"
            )

        # 6. Risk level gate
        if signal.risk_level == "extreme":
            result.passed = False
            result.reasons.append("Risk level is EXTREME — trade blocked")

        # 7. Shorting / options check
        if signal.trade_decision in ("SHORT", "COVER") and not s.allow_shorting:
            result.passed = False
            result.reasons.append("Shorting is disabled in config")

        # 8. Daily loss limit
        if self._daily_loss_usd >= s.max_daily_loss_usd:
            result.passed = False
            result.reasons.append(
                f"Daily loss limit reached: ${self._daily_loss_usd:.2f} >= ${s.max_daily_loss_usd}"
            )

        # 9. Max open positions
        if open_position_count >= s.max_open_positions:
            if signal.trade_decision == "BUY":
                result.passed = False
                result.reasons.append(
                    f"Max open positions reached: {open_position_count}/{s.max_open_positions}"
                )

        # 10. Max trades per ticker per day (default 3)
        ticker_trades = self._trades_per_ticker_today.get(signal.ticker, 0)
        if ticker_trades >= 3:
            result.passed = False
            result.reasons.append(
                f"Max trades for {signal.ticker} today: {ticker_trades}/3"
            )

        # 11. Cooldown check
        cooldown = self._cooldown_until.get(signal.ticker)
        if cooldown and datetime.now(timezone.utc) < cooldown:
            result.passed = False
            result.reasons.append(
                f"{signal.ticker} in cooldown until {cooldown.strftime('%H:%M:%S UTC')}"
            )

        # 12. Trade size calculation
        if result.passed and current_price > 0:
            max_spend = min(s.max_trade_size_usd, account_cash * 0.1)  # max 10% of cash
            if max_spend < current_price:
                result.passed = False
                result.reasons.append(
                    f"Trade size too small: max ${max_spend:.2f} < share price ${current_price:.2f}"
                )
            else:
                qty = max_spend / current_price
                result.suggested_quantity = max(0.01, round(qty, 4))
                result.suggested_stop_loss = round(current_price * 0.97, 2)  # 3% stop
                result.suggested_take_profit = round(current_price * 1.05, 2)  # 5% target

        # 13. Price sanity (no penny stocks in paper mode for safety)
        if current_price < 1.0:
            result.passed = False
            result.warnings.append(f"Penny stock detected (${current_price:.4f}) — blocked")

        if not result.passed and not result.reasons:
            result.reasons.append("Unknown risk check failure")

        return result

    # ------------------------------------------------------------------
    # Status report
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        self._maybe_reset_daily_counters()
        s = self._settings
        return {
            "bot_running": self._bot_running and not self._emergency_stopped and not self._manual_paused,
            "paper_mode": s.is_paper_mode,
            "emergency_stopped": self._emergency_stopped,
            "manually_paused": self._manual_paused,
            "daily_loss_usd": round(self._daily_loss_usd, 2),
            "max_daily_loss_usd": s.max_daily_loss_usd,
            "daily_loss_pct": round(
                (self._daily_loss_usd / s.max_daily_loss_usd * 100) if s.max_daily_loss_usd else 0, 1
            ),
            "trades_today": self._trades_today,
            "max_daily_loss_remaining": round(
                max(0, s.max_daily_loss_usd - self._daily_loss_usd), 2
            ),
        }
