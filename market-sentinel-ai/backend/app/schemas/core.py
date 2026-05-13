"""Pydantic response/request schemas."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Enums ---

class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    SHORT = "SHORT"
    COVER = "COVER"
    HOLD = "HOLD"
    ALERT_ONLY = "ALERT_ONLY"
    IGNORE = "IGNORE"


class RecommendedAction(str, Enum):
    TRADE_ALLOWED = "TRADE_ALLOWED"
    ALERT_ONLY = "ALERT_ONLY"
    IGNORE = "IGNORE"


# --- Watchlist ---

class WatchlistTickerCreate(BaseModel):
    ticker: str
    name: str | None = None
    sector: str | None = None
    max_position_usd: float | None = None
    notes: str | None = None


class WatchlistTickerOut(_Base):
    id: str
    ticker: str
    name: str | None
    sector: str | None
    is_active: bool
    max_position_usd: float | None
    notes: str | None
    created_at: datetime


# --- Source Items ---

class SourceItemOut(_Base):
    id: str
    source_name: str
    source_type: str
    source_url: str | None
    author: str | None
    published_at: datetime | None
    collected_at: datetime
    ticker_detected: str | None
    headline: str | None
    is_processed: bool


# --- Verified Events ---

class VerifiedEventOut(_Base):
    id: str
    ticker: str
    event_type: str
    sentiment: str
    credibility_score: float
    corroboration_score: float
    duplicate_story_score: float
    market_reaction_score: float
    final_confidence_score: float
    recommended_action: str
    verification_notes: str | None
    created_at: datetime


# --- AI Signals ---

class AISignalOut(_Base):
    id: str
    ticker: str
    event_summary: str
    event_type: str
    sentiment: str
    confidence: float
    expected_time_horizon: str
    expected_price_impact: str
    risk_level: str
    trade_decision: str
    reasoning_summary: str
    sources_used: list[str] | None
    model_used: str | None
    created_at: datetime


# --- Trade Decisions ---

class TradeDecisionOut(_Base):
    id: str
    ticker: str
    action: str
    quantity: float | None
    target_price: float | None
    stop_loss_price: float | None
    take_profit_price: float | None
    risk_check_passed: bool
    risk_check_notes: str | None
    paper_mode: bool
    executed: bool
    ignored_reason: str | None
    created_at: datetime


# --- Orders ---

class OrderOut(_Base):
    id: str
    broker_order_id: str | None
    ticker: str
    side: str
    order_type: str
    quantity: float
    limit_price: float | None
    filled_price: float | None
    filled_quantity: float | None
    status: str
    paper_mode: bool
    submitted_at: datetime | None
    filled_at: datetime | None
    error_message: str | None
    created_at: datetime


# --- Positions ---

class PositionSnapshotOut(_Base):
    id: str
    ticker: str
    quantity: float
    avg_entry_price: float
    current_price: float
    market_value: float
    unrealized_pl: float
    unrealized_pl_pct: float
    paper_mode: bool
    snapshot_at: datetime


# --- Portfolio ---

class PortfolioSnapshotOut(_Base):
    id: str
    account_value: float
    cash_balance: float
    positions_value: float
    unrealized_pl: float
    realized_pl_today: float
    daily_pl: float
    trades_today: int
    open_positions: int
    paper_mode: bool
    snapshot_at: datetime


# --- Risk ---

class RiskEventOut(_Base):
    id: str
    event_type: str
    severity: str
    ticker: str | None
    description: str
    triggered_value: float | None
    limit_value: float | None
    action_taken: str | None
    created_at: datetime


class RiskStatusOut(BaseModel):
    bot_running: bool
    paper_mode: bool
    emergency_stopped: bool
    daily_loss_usd: float
    max_daily_loss_usd: float
    daily_loss_pct: float
    open_positions: int
    max_open_positions: int
    trades_today: int
    trading_allowed: bool
    market_open: bool
    risk_warnings: list[str]


# --- Reports ---

class DailyReportOut(_Base):
    id: str
    report_date: str
    account_value: float
    cash_balance: float
    daily_pl: float
    realized_pl: float
    unrealized_pl: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    signals_generated: int
    signals_traded: int
    signals_alerted: int
    signals_ignored: int
    best_trade_ticker: str | None
    best_trade_pl: float | None
    worst_trade_ticker: str | None
    worst_trade_pl: float | None
    risk_events_count: int
    paper_mode: bool
    sent_telegram: bool
    sent_email: bool
    created_at: datetime


# --- Bot Status ---

class BotStatusOut(BaseModel):
    running: bool
    paper_mode: bool
    emergency_stopped: bool
    market_open: bool
    account_value: float
    cash_balance: float
    daily_pl: float
    open_positions: int
    trades_today: int
    signals_today: int
    last_updated: datetime


# --- Overview ---

class OverviewOut(BaseModel):
    bot_status: BotStatusOut
    portfolio: PortfolioSnapshotOut | None
    recent_signals: list[AISignalOut]
    recent_trades: list[TradeDecisionOut]
    risk_status: RiskStatusOut


# --- Backtest ---

class BacktestRequest(BaseModel):
    tickers: list[str]
    start_date: str  # YYYY-MM-DD
    end_date: str
    initial_capital: float = 10000.0
    strategy: str = "news_momentum"


class BacktestResult(BaseModel):
    strategy: str
    tickers: list[str]
    start_date: str
    end_date: str
    initial_capital: float
    final_capital: float
    total_return_pct: float
    win_rate_pct: float
    max_drawdown_pct: float
    avg_win: float
    avg_loss: float
    sharpe_ratio: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    best_trade: dict[str, Any] | None
    worst_trade: dict[str, Any] | None
    equity_curve: list[dict[str, Any]]


# --- System Logs ---

class SystemLogOut(_Base):
    id: str
    level: str
    component: str
    message: str
    ticker: str | None
    data: dict[str, Any] | None
    created_at: datetime
