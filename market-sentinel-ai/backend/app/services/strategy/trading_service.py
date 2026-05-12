"""
Trading Service — orchestrates the full pipeline:
  SourceItem → Verification → AI Analysis → Risk Check → Order Execution
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    AISignal,
    Order,
    SourceItem,
    SystemLog,
    TradeDecision,
    VerifiedEvent,
    WatchlistTicker,
)
from app.schemas.core import AISignalOut
from app.services.ai_analysis.analyzer import AIAnalyzer
from app.services.broker.base import BrokerClient
from app.services.risk.engine import RiskEngine
from app.services.verification.engine import VerificationEngine

logger = logging.getLogger(__name__)


class TradingService:
    """End-to-end pipeline from raw source items to executed (paper) orders."""

    def __init__(
        self,
        db: AsyncSession,
        broker: BrokerClient,
        risk_engine: RiskEngine,
    ) -> None:
        self._db = db
        self._broker = broker
        self._risk = risk_engine
        self._verifier = VerificationEngine()
        self._analyzer = AIAnalyzer()

    async def process_unprocessed_items(self) -> int:
        """Process all unprocessed SourceItems. Returns number processed."""
        result = await self._db.execute(
            select(SourceItem).where(SourceItem.is_processed.is_(False)).limit(50)
        )
        items = list(result.scalars().all())
        count = 0
        for item in items:
            try:
                await self._process_item(item)
                item.is_processed = True
                count += 1
            except Exception as e:
                logger.error("Failed to process source item %s: %s", item.id, e)
                await self._log("ERROR", "trading_service", f"Process item error: {e}", item.ticker_detected)

        await self._db.flush()
        return count

    async def _process_item(self, item: SourceItem) -> None:
        ticker = item.ticker_detected
        if not ticker:
            return

        # Check ticker is in active watchlist
        wl = await self._db.execute(
            select(WatchlistTicker).where(
                WatchlistTicker.ticker == ticker,
                WatchlistTicker.is_active.is_(True),
            )
        )
        if not wl.scalar_one_or_none():
            logger.debug("Ticker %s not in active watchlist — skipping", ticker)
            return

        # --- 1. VERIFICATION ---
        ver_result = self._verifier.verify(
            source_id=item.id,
            source_name=item.source_name,
            source_type=item.source_type,
            ticker=ticker,
            headline=item.headline or "",
            content=item.content,
            published_at=item.published_at,
        )

        verified_event = VerifiedEvent(
            source_item_id=item.id,
            ticker=ticker,
            event_type=ver_result.event_type,
            sentiment=ver_result.sentiment,
            credibility_score=ver_result.credibility_score,
            corroboration_score=ver_result.corroboration_score,
            duplicate_story_score=ver_result.duplicate_story_score,
            market_reaction_score=ver_result.market_reaction_score,
            final_confidence_score=ver_result.final_confidence_score,
            recommended_action=ver_result.recommended_action,
            corroborating_source_ids=ver_result.corroborating_source_ids,
            verification_notes=ver_result.verification_notes,
        )
        self._db.add(verified_event)
        await self._db.flush()  # Get ID

        if ver_result.recommended_action == "IGNORE":
            await self._log(
                "INFO", "verification", f"{ticker}: Ignored — {ver_result.verification_notes}", ticker
            )
            return

        # --- 2. AI ANALYSIS ---
        ai_input = {
            "ticker": ticker,
            "headline": item.headline,
            "content": item.content,
            "source_type": item.source_type,
            "source_name": item.source_name,
            "published_at": str(item.published_at) if item.published_at else None,
            "sentiment": ver_result.sentiment,
            "confidence_score": ver_result.final_confidence_score,
            "credibility_score": ver_result.credibility_score,
            "corroboration_count": len(ver_result.corroborating_source_ids) + 1,
            "event_type": ver_result.event_type,
            "market_open": await self._broker.is_market_open(),
        }
        ai_raw = await self._analyzer.analyze(ai_input)

        ai_signal = AISignal(
            verified_event_id=verified_event.id,
            ticker=ticker,
            event_summary=ai_raw.get("event_summary", item.headline or "")[:2048],
            event_type=ai_raw.get("event_type", ver_result.event_type),
            sentiment=ai_raw.get("sentiment", ver_result.sentiment),
            confidence=float(ai_raw.get("confidence", ver_result.final_confidence_score)),
            expected_time_horizon=ai_raw.get("expected_time_horizon", "hours"),
            expected_price_impact=ai_raw.get("expected_price_impact", "low"),
            risk_level=ai_raw.get("risk_level", "medium"),
            trade_decision=ai_raw.get("trade_decision", "HOLD"),
            reasoning_summary=ai_raw.get("reasoning_summary", "")[:4096],
            sources_used=ai_raw.get("sources_used", []),
            model_used=ai_raw.get("model_used"),
            raw_ai_response=ai_raw.get("raw_ai_response"),
        )
        self._db.add(ai_signal)
        await self._db.flush()

        # Alert-only: log and notify but no trade
        if ai_signal.trade_decision in ("ALERT_ONLY", "HOLD", "IGNORE"):
            await self._log(
                "INFO",
                "ai_analysis",
                f"{ticker}: Signal={ai_signal.trade_decision} confidence={ai_signal.confidence:.0f}",
                ticker,
            )
            return

        # --- 3. RISK CHECK ---
        signal_out = AISignalOut.model_validate(ai_signal)
        market_open = await self._broker.is_market_open()
        account = await self._broker.get_account()
        positions = await self._broker.get_positions()
        current_price = await self._broker.get_current_price(ticker) or 0

        risk_result = await self._risk.check_trade(
            signal=signal_out,
            current_price=current_price,
            account_cash=account.cash,
            open_position_count=len(positions),
            market_open=market_open,
        )

        trade_decision = TradeDecision(
            ai_signal_id=ai_signal.id,
            ticker=ticker,
            action=ai_signal.trade_decision if risk_result.passed else "IGNORED",
            quantity=risk_result.suggested_quantity,
            target_price=current_price,
            stop_loss_price=risk_result.suggested_stop_loss,
            take_profit_price=risk_result.suggested_take_profit,
            risk_check_passed=risk_result.passed,
            risk_check_notes=risk_result.notes,
            paper_mode=self._broker.is_paper,
            executed=False,
            ignored_reason=None if risk_result.passed else risk_result.notes,
        )
        self._db.add(trade_decision)
        await self._db.flush()

        if not risk_result.passed:
            await self._log(
                "WARNING",
                "risk_engine",
                f"{ticker}: Trade BLOCKED — {risk_result.notes}",
                ticker,
            )
            return

        # --- 4. EXECUTE PAPER ORDER ---
        await self._execute_order(trade_decision, ai_signal, current_price)

    async def _execute_order(
        self, decision: TradeDecision, signal: AISignal, current_price: float
    ) -> None:
        ticker = decision.ticker
        side = "buy" if decision.action == "BUY" else "sell"
        qty = decision.quantity or 1.0

        logger.info(
            "Executing PAPER %s order: %s x%s @ ~$%.2f",
            side.upper(), ticker, qty, current_price,
        )

        broker_order = await self._broker.submit_market_order(
            ticker=ticker,
            side=side,
            quantity=qty,
            paper_mode=decision.paper_mode,
        )

        order = Order(
            trade_decision_id=decision.id,
            broker_order_id=broker_order.broker_order_id,
            ticker=ticker,
            side=side,
            order_type="market",
            quantity=qty,
            filled_price=broker_order.filled_price,
            filled_quantity=broker_order.filled_quantity,
            status=broker_order.status,
            paper_mode=decision.paper_mode,
            submitted_at=broker_order.submitted_at or datetime.now(timezone.utc),
            filled_at=broker_order.filled_at,
            error_message=broker_order.error_message,
        )
        self._db.add(order)

        if broker_order.status == "filled":
            decision.executed = True
            # Set cooldown to prevent churning
            self._risk.set_cooldown(ticker, seconds=300)
            await self._log(
                "INFO",
                "execution",
                f"Order FILLED: {side.upper()} {qty} {ticker} @ ${broker_order.filled_price}",
                ticker,
                {"order_id": broker_order.broker_order_id, "signal_id": signal.id},
            )
        else:
            await self._log(
                "WARNING",
                "execution",
                f"Order {broker_order.status}: {side.upper()} {qty} {ticker} — {broker_order.error_message}",
                ticker,
            )

        await self._db.flush()

    async def _log(
        self,
        level: str,
        component: str,
        message: str,
        ticker: str | None = None,
        data: dict | None = None,
    ) -> None:
        log = SystemLog(level=level, component=component, message=message, ticker=ticker, data=data)
        self._db.add(log)
