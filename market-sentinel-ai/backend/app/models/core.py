"""SQLAlchemy ORM models for Market Sentinel AI."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class UserConfig(TimestampMixin, Base):
    """Global bot configuration persisted in DB (overrides env defaults at runtime)."""

    __tablename__ = "user_config"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class WatchlistTicker(TimestampMixin, Base):
    """Tickers the bot monitors and may trade."""

    __tablename__ = "watchlist_ticker"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(256))
    sector: Mapped[str | None] = mapped_column(String(128))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    max_position_usd: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)


class SourceItem(TimestampMixin, Base):
    """Raw collected data item from any source before verification."""

    __tablename__ = "source_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False)
    source_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # news|sec|social|price|earnings
    source_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(256))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ticker_detected: Mapped[str | None] = mapped_column(String(16), index=True)
    headline: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    dedup_hash: Mapped[str | None] = mapped_column(String(64), index=True)


class VerifiedEvent(TimestampMixin, Base):
    """A source item that has been through the verification engine."""

    __tablename__ = "verified_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_item_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_item.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False)

    # Scoring fields
    credibility_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    corroboration_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    duplicate_story_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    market_reaction_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    final_confidence_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    recommended_action: Mapped[str] = mapped_column(
        String(32), nullable=False, default="IGNORE"
    )  # TRADE_ALLOWED|ALERT_ONLY|IGNORE

    corroborating_source_ids: Mapped[list[str] | None] = mapped_column(JSON)
    verification_notes: Mapped[str | None] = mapped_column(Text)

    source_item: Mapped[SourceItem] = relationship("SourceItem", lazy="select")
    ai_signals: Mapped[list[AISignal]] = relationship(
        "AISignal", back_populates="verified_event", lazy="select"
    )


class AISignal(TimestampMixin, Base):
    """AI analysis output for a verified event."""

    __tablename__ = "ai_signal"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    verified_event_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("verified_event.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    event_summary: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    expected_time_horizon: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_price_impact: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False)
    trade_decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False)
    sources_used: Mapped[list[str] | None] = mapped_column(JSON)
    raw_ai_response: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    model_used: Mapped[str | None] = mapped_column(String(128))

    verified_event: Mapped[VerifiedEvent] = relationship(
        "VerifiedEvent", back_populates="ai_signals", lazy="select"
    )
    trade_decisions: Mapped[list[TradeDecision]] = relationship(
        "TradeDecision", back_populates="ai_signal", lazy="select"
    )


class TradeDecision(TimestampMixin, Base):
    """Final trade decision after risk engine review of AI signal."""

    __tablename__ = "trade_decision"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ai_signal_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_signal.id"), nullable=False
    )
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    action: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # BUY|SELL|SHORT|COVER|HOLD|ALERT_ONLY|IGNORED
    quantity: Mapped[float | None] = mapped_column(Float)
    target_price: Mapped[float | None] = mapped_column(Float)
    stop_loss_price: Mapped[float | None] = mapped_column(Float)
    take_profit_price: Mapped[float | None] = mapped_column(Float)
    risk_check_passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    risk_check_notes: Mapped[str | None] = mapped_column(Text)
    paper_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ignored_reason: Mapped[str | None] = mapped_column(Text)

    ai_signal: Mapped[AISignal] = relationship(
        "AISignal", back_populates="trade_decisions", lazy="select"
    )
    orders: Mapped[list[Order]] = relationship(
        "Order", back_populates="trade_decision", lazy="select"
    )


class Order(TimestampMixin, Base):
    """Broker order record (paper or live)."""

    __tablename__ = "order"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    trade_decision_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("trade_decision.id")
    )
    broker_order_id: Mapped[str | None] = mapped_column(String(128), index=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    side: Mapped[str] = mapped_column(String(8), nullable=False)  # buy|sell
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)  # market|limit
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Float)
    filled_price: Mapped[float | None] = mapped_column(Float)
    filled_quantity: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending"
    )  # pending|filled|cancelled|rejected
    paper_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)

    trade_decision: Mapped[TradeDecision | None] = relationship(
        "TradeDecision", back_populates="orders", lazy="select"
    )


class PositionSnapshot(TimestampMixin, Base):
    """Point-in-time snapshot of a single open position."""

    __tablename__ = "position_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    avg_entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    current_price: Mapped[float] = mapped_column(Float, nullable=False)
    market_value: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pl_pct: Mapped[float] = mapped_column(Float, nullable=False)
    paper_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PortfolioSnapshot(TimestampMixin, Base):
    """Point-in-time snapshot of the full portfolio."""

    __tablename__ = "portfolio_snapshot"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    account_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False)
    positions_value: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pl: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pl_today: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    daily_pl: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    trades_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    open_positions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paper_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RiskEvent(TimestampMixin, Base):
    """Risk management events: limit breaches, emergency stops, pauses."""

    __tablename__ = "risk_event"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # daily_loss_limit|position_limit|emergency_stop|manual_pause|etc
    severity: Mapped[str] = mapped_column(String(16), nullable=False)  # info|warning|critical
    ticker: Mapped[str | None] = mapped_column(String(16))
    description: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_value: Mapped[float | None] = mapped_column(Float)
    limit_value: Mapped[float | None] = mapped_column(Float)
    action_taken: Mapped[str | None] = mapped_column(Text)


class DailyReport(TimestampMixin, Base):
    """End-of-day summary report."""

    __tablename__ = "daily_report"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    report_date: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    account_value: Mapped[float] = mapped_column(Float, nullable=False)
    cash_balance: Mapped[float] = mapped_column(Float, nullable=False)
    daily_pl: Mapped[float] = mapped_column(Float, nullable=False)
    realized_pl: Mapped[float] = mapped_column(Float, nullable=False)
    unrealized_pl: Mapped[float] = mapped_column(Float, nullable=False)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_traded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_alerted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signals_ignored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    best_trade_ticker: Mapped[str | None] = mapped_column(String(16))
    best_trade_pl: Mapped[float | None] = mapped_column(Float)
    worst_trade_ticker: Mapped[str | None] = mapped_column(String(16))
    worst_trade_pl: Mapped[float | None] = mapped_column(Float)
    risk_events_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    paper_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    report_data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    sent_telegram: Mapped[bool] = mapped_column(Boolean, default=False)
    sent_email: Mapped[bool] = mapped_column(Boolean, default=False)


class SystemLog(TimestampMixin, Base):
    """Audit log for all significant system actions."""

    __tablename__ = "system_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    level: Mapped[str] = mapped_column(String(16), nullable=False)  # DEBUG|INFO|WARNING|ERROR
    component: Mapped[str] = mapped_column(String(64), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(16), index=True)
    data: Mapped[dict[str, Any] | None] = mapped_column(JSON)
