"""
Trading Service — orchestrates the full pipeline:
  SourceItem → Verification → AI Analysis → Strategy → Risk Check → Order Execution
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.core import (
    AISignal,
    Order,
    RiskEvent,
    SourceItem,
    SystemLog,
    TradeDecision,
    VerifiedEvent,
    WatchlistTicker,
)
from app.schemas.core import AISignalOut
from app.services.ai_analysis.analyzer import AIAnalyzer
from app.services.broker.base import BrokerClient
from app.services.reporting.reporter import ReportingService
from app.services.risk.engine import RiskEngine
from app.services.strategy.strategies import DEFAULT_ACTIVE_STRATEGIES, evaluate_strategies
from app.services.verification.engine import VerificationEngine
from app.ws.manager import ws_manager

logger = logging.getLogger(__name__)


class TradingService:
    """End-to-end pipeline from raw source items to executed (paper) orders."""

    def __init__(
        self,
        db: AsyncSession,
        broker: BrokerClient,
        risk_engine: RiskEngine,
        active_strategies: list[str] | None = None,
        reporter: ReportingService | None = None,
    ) -> None:
        self._db = db
        self._broker = broker
        self._risk = risk_engine
        self._verifier = VerificationEngine()
        self._analyzer = AIAnalyzer()
        self._reporter = reporter or ReportingService()
        self._strategies = active_strategies or DEFAULT_ACTIVE_STRATEGIES

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
        await self._db.flush()

        if ver_result.recommended_action == "IGNORE":
            await self._log("INFO", "verification", f"{ticker}: Ignored — {ver_result.verification_notes}", ticker)
            return

        # --- 2. AI ANALYSIS ---
        market_open = await self._broker.is_market_open()
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
            "market_open": market_open,
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

        await self._log(
            "INFO",
            "ai_analysis",
            f"{ticker}: AI={ai_signal.trade_decision} conf={ai_signal.confidence:.0f}% risk={ai_signal.risk_level}",
            ticker,
        )

        # Broadcast signal event to dashboard clients
        await ws_manager.broadcast("signal", {
            "id": ai_signal.id,
            "ticker": ai_signal.ticker,
            "trade_decision": ai_signal.trade_decision,
            "confidence": ai_signal.confidence,
            "sentiment": ai_signal.sentiment,
            "risk_level": ai_signal.risk_level,
            "event_summary": ai_signal.event_summary[:200],
        })

        # Alert-only signals — send notification but don't trade
        if ai_signal.trade_decision in ("ALERT_ONLY", "IGNORE"):
            if ai_signal.confidence >= 50:
                await self._send_alert_notification(ai_signal)
            return

        # --- 3. STRATEGY FILTER ---
        signal_out = AISignalOut.model_validate(ai_signal)
        strategy_decision = evaluate_strategies(signal_out, self._strategies)

        if not strategy_decision.should_trade:
            ai_signal.trade_decision = strategy_decision.action
            await self._log(
                "INFO",
                "strategy",
                f"{ticker}: Strategy blocked — {strategy_decision.reason}",
                ticker,
            )
            if strategy_decision.action == "ALERT_ONLY" and ai_signal.confidence >= 50:
                await self._send_alert_notification(ai_signal)
            return

        # --- 4. RISK CHECK ---
        account = await self._broker.get_account()
        positions = await self._broker.get_positions()
        current_price = await self._broker.get_current_price(ticker) or 0.0

        risk_result = await self._risk.check_trade(
            signal=signal_out,
            current_price=current_price,
            account_cash=account.cash,
            open_position_count=len(positions),
            market_open=market_open,
        )

        # Apply strategy size multiplier to suggested quantity
        if risk_result.passed and risk_result.suggested_quantity and strategy_decision.size_multiplier != 1.0:
            risk_result.suggested_quantity = round(
                risk_result.suggested_quantity * strategy_decision.size_multiplier, 4
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
            risk_check_notes=f"[{strategy_decision.reason}] {risk_result.notes}",
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
            # Log as risk event if it's a limit breach
            if any(kw in risk_result.notes for kw in ("Daily loss", "Max open", "Emergency")):
                risk_event = RiskEvent(
                    event_type="trade_blocked",
                    severity="warning",
                    ticker=ticker,
                    description=risk_result.notes,
                    action_taken="Trade cancelled",
                )
                self._db.add(risk_event)
            return

        # --- 5. EXECUTE PAPER ORDER ---
        await self._execute_order(trade_decision, ai_signal, current_price)

    async def _execute_order(
        self, decision: TradeDecision, signal: AISignal, current_price: float
    ) -> None:
        ticker = decision.ticker
        side = "buy" if decision.action == "BUY" else "sell"
        qty = decision.quantity or 1.0

        logger.info(
            "Executing PAPER %s: %s x%.4f @ ~$%.2f (conf=%.0f%%)",
            side.upper(), ticker, qty, current_price, signal.confidence,
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
            self._risk.set_cooldown(ticker, seconds=300)

            await self._log(
                "INFO",
                "execution",
                f"FILLED: {side.upper()} {qty:.4f} {ticker} @ ${broker_order.filled_price:.2f}",
                ticker,
                {"order_id": broker_order.broker_order_id, "signal_id": signal.id},
            )

            # Broadcast trade event to dashboard clients
            await ws_manager.broadcast("trade", {
                "ticker": ticker,
                "side": side,
                "quantity": qty,
                "price": broker_order.filled_price or current_price,
                "status": broker_order.status,
                "paper_mode": decision.paper_mode,
            })

            # Send trade execution alert
            await self._reporter.send_telegram(
                self._reporter.format_trade_alert_telegram(
                    action=decision.action,
                    ticker=ticker,
                    quantity=qty,
                    price=broker_order.filled_price or current_price,
                    confidence=signal.confidence,
                    reasoning=signal.reasoning_summary,
                    paper_mode=decision.paper_mode,
                )
            )
        else:
            await self._log(
                "WARNING",
                "execution",
                f"Order {broker_order.status}: {side.upper()} {qty} {ticker} — {broker_order.error_message}",
                ticker,
            )

        await self._db.flush()

    async def _send_alert_notification(self, signal: AISignal) -> None:
        """Send a non-trade alert for significant events."""
        mode = "📄 PAPER" if self._broker.is_paper else "💰 LIVE"
        sentiment_emoji = {"positive": "🟢", "negative": "🔴", "mixed": "🟡", "neutral": "⚪"}.get(
            signal.sentiment, "⚪"
        )
        msg = (
            f"<b>{mode} | {sentiment_emoji} Market Alert</b>\n"
            f"Ticker: <b>{signal.ticker}</b>\n"
            f"Event: {signal.event_type.replace('_', ' ').title()}\n"
            f"Confidence: {signal.confidence:.0f}%\n"
            f"Signal: {signal.trade_decision}\n"
            f"Summary: {signal.event_summary[:200]}\n\n"
            f"<i>No trade executed — alert only.</i>"
        )
        await self._reporter.send_telegram(msg)

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
