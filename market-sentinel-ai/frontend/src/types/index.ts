export interface BotStatus {
  running: boolean
  paper_mode: boolean
  emergency_stopped: boolean
  market_open: boolean
  account_value: number
  cash_balance: number
  daily_pl: number
  open_positions: number
  trades_today: number
  signals_today: number
  last_updated: string
}

export interface RiskStatus {
  bot_running: boolean
  paper_mode: boolean
  emergency_stopped: boolean
  daily_loss_usd: number
  max_daily_loss_usd: number
  daily_loss_pct: number
  open_positions: number
  max_open_positions: number
  trades_today: number
  trading_allowed: boolean
  market_open: boolean
  risk_warnings: string[]
}

export interface PortfolioSnapshot {
  id: string
  account_value: number
  cash_balance: number
  positions_value: number
  unrealized_pl: number
  realized_pl_today: number
  daily_pl: number
  trades_today: number
  open_positions: number
  paper_mode: boolean
  snapshot_at: string
}

export interface AISignal {
  id: string
  ticker: string
  event_summary: string
  event_type: string
  sentiment: 'positive' | 'negative' | 'neutral' | 'mixed'
  confidence: number
  expected_time_horizon: string
  expected_price_impact: string
  risk_level: 'low' | 'medium' | 'high' | 'extreme'
  trade_decision: string
  reasoning_summary: string
  sources_used: string[] | null
  model_used: string | null
  created_at: string
}

export interface TradeDecision {
  id: string
  ticker: string
  action: string
  quantity: number | null
  target_price: number | null
  stop_loss_price: number | null
  take_profit_price: number | null
  risk_check_passed: boolean
  risk_check_notes: string | null
  paper_mode: boolean
  executed: boolean
  ignored_reason: string | null
  created_at: string
}

export interface PositionSnapshot {
  id: string
  ticker: string
  quantity: number
  avg_entry_price: number
  current_price: number
  market_value: number
  unrealized_pl: number
  unrealized_pl_pct: number
  paper_mode: boolean
  snapshot_at: string
}

export interface SourceItem {
  id: string
  source_name: string
  source_type: string
  source_url: string | null
  author: string | null
  published_at: string | null
  collected_at: string
  ticker_detected: string | null
  headline: string | null
  is_processed: boolean
}

export interface VerifiedEvent {
  id: string
  ticker: string
  event_type: string
  sentiment: string
  credibility_score: number
  corroboration_score: number
  duplicate_story_score: number
  market_reaction_score: number
  final_confidence_score: number
  recommended_action: 'TRADE_ALLOWED' | 'ALERT_ONLY' | 'IGNORE'
  verification_notes: string | null
  created_at: string
}

export interface DailyReport {
  id: string
  report_date: string
  account_value: number
  cash_balance: number
  daily_pl: number
  realized_pl: number
  unrealized_pl: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  signals_generated: number
  signals_traded: number
  signals_alerted: number
  signals_ignored: number
  best_trade_ticker: string | null
  best_trade_pl: number | null
  worst_trade_ticker: string | null
  worst_trade_pl: number | null
  risk_events_count: number
  paper_mode: boolean
  sent_telegram: boolean
  sent_email: boolean
  created_at: string
}

export interface WatchlistTicker {
  id: string
  ticker: string
  name: string | null
  sector: string | null
  is_active: boolean
  max_position_usd: number | null
  notes: string | null
  created_at: string
}

export interface OverviewData {
  bot_status: BotStatus
  portfolio: PortfolioSnapshot | null
  recent_signals: AISignal[]
  recent_trades: TradeDecision[]
  risk_status: RiskStatus
}

export interface BacktestRequest {
  tickers: string[]
  start_date: string
  end_date: string
  initial_capital: number
  strategy: string
}

export interface BacktestResult {
  strategy: string
  tickers: string[]
  start_date: string
  end_date: string
  initial_capital: number
  final_capital: number
  total_return_pct: number
  win_rate_pct: number
  max_drawdown_pct: number
  avg_win: number
  avg_loss: number
  sharpe_ratio: number
  total_trades: number
  winning_trades: number
  losing_trades: number
  best_trade: { ticker: string; pnl: number; date: string } | null
  worst_trade: { ticker: string; pnl: number; date: string } | null
  equity_curve: { date: string; equity: number }[]
}
