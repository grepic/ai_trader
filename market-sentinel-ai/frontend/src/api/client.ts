import type {
  AISignal,
  BacktestRequest,
  BacktestResult,
  DailyReport,
  OverviewData,
  PositionSnapshot,
  PortfolioSnapshot,
  RiskStatus,
  SourceItem,
  SystemLog,
  TradeDecision,
  VerifiedEvent,
  WatchlistTicker,
} from '../types'

const BASE = ''  // same origin via Vite proxy

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!resp.ok) {
    const err = await resp.text()
    throw new Error(`${resp.status}: ${err}`)
  }
  if (resp.status === 204) return undefined as T
  return resp.json()
}

// --- Overview ---
export const getOverview = () => request<OverviewData>('/api/overview')
export const getHealth = () => request<{ status: string }>('/health')

// --- Signals ---
export const getSignals = (limit = 50, ticker?: string) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (ticker) params.set('ticker', ticker)
  return request<AISignal[]>(`/api/signals?${params}`)
}
export const getSignal = (id: string) => request<AISignal>(`/api/signals/${id}`)

// --- Trades ---
export const getTrades = (limit = 50, executedOnly = false) => {
  const params = new URLSearchParams({ limit: String(limit), executed_only: String(executedOnly) })
  return request<TradeDecision[]>(`/api/trades?${params}`)
}

// --- Positions ---
export const getPositions = () => request<PositionSnapshot[]>('/api/positions')
export const getPortfolio = () => request<PortfolioSnapshot>('/api/positions/portfolio')

// --- Sources ---
export const getSources = (limit = 50, ticker?: string) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (ticker) params.set('ticker', ticker)
  return request<SourceItem[]>(`/api/sources?${params}`)
}
export const getVerifiedEvents = (limit = 50) =>
  request<VerifiedEvent[]>(`/api/sources/verified?limit=${limit}`)

// --- Risk ---
export const getRiskStatus = () => request<RiskStatus>('/api/risk/status')
export const pauseBot = () => request<{ status: string }>('/api/bot/pause', { method: 'POST' })
export const resumeBot = () => request<{ status: string }>('/api/bot/resume', { method: 'POST' })
export const emergencyStop = () =>
  request<{ status: string; positions_closed: string[] }>('/api/bot/emergency-stop', {
    method: 'POST',
  })

// --- Watchlist ---
export const getWatchlist = () => request<WatchlistTicker[]>('/api/watchlist')
export const addTicker = (payload: { ticker: string; name?: string; sector?: string }) =>
  request<WatchlistTicker>('/api/watchlist', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
export const removeTicker = (ticker: string) =>
  request<void>(`/api/watchlist/${ticker}`, { method: 'DELETE' })

// --- Reports ---
export const getDailyReports = (limit = 30) =>
  request<DailyReport[]>(`/api/reports/daily?limit=${limit}`)

// --- Logs ---
export const getLogs = (limit = 200, level?: string, component?: string, ticker?: string) => {
  const params = new URLSearchParams({ limit: String(limit) })
  if (level) params.set('level', level)
  if (component) params.set('component', component)
  if (ticker) params.set('ticker', ticker)
  return request<SystemLog[]>(`/api/logs?${params}`)
}

// --- Backtest ---
export const runBacktest = (payload: BacktestRequest) =>
  request<BacktestResult>('/api/backtest/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
