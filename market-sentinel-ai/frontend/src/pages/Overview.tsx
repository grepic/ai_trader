import {
  Activity,
  AlertCircle,
  AlertTriangle,
  BarChart2,
  CheckCircle,
  DollarSign,
  TrendingDown,
  TrendingUp,
  Zap,
} from 'lucide-react'
import { getOverview } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card, StatCard } from '../components/ui/Card'
import type { AISignal } from '../types'

function fmt(n: number, prefix = '$') {
  return `${prefix}${Math.abs(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

function SignalRow({ s }: { s: AISignal }) {
  const sentimentVariant = {
    positive: 'green',
    negative: 'red',
    neutral: 'gray',
    mixed: 'yellow',
  }[s.sentiment] as 'green' | 'red' | 'gray' | 'yellow'

  const decisionVariant: Record<string, 'green' | 'red' | 'yellow' | 'gray' | 'blue'> = {
    BUY: 'green',
    SELL: 'red',
    SHORT: 'red',
    ALERT_ONLY: 'yellow',
    HOLD: 'gray',
    IGNORE: 'gray',
  }

  return (
    <div className="flex items-start gap-3 py-2 border-b border-gray-50 last:border-0">
      <div className="mt-0.5 shrink-0">
        <span className="font-bold text-sm text-gray-800 bg-gray-100 px-2 py-0.5 rounded">
          {s.ticker}
        </span>
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-700 truncate">{s.event_summary}</p>
        <div className="flex items-center gap-2 mt-1 flex-wrap">
          <Badge label={s.sentiment} variant={sentimentVariant} />
          <Badge
            label={s.trade_decision}
            variant={decisionVariant[s.trade_decision] ?? 'gray'}
          />
          <span className="text-xs text-gray-400">{s.confidence.toFixed(0)}% conf.</span>
        </div>
      </div>
      <span className="text-xs text-gray-400 shrink-0">
        {new Date(s.created_at).toLocaleTimeString()}
      </span>
    </div>
  )
}

export function Overview() {
  const { data, loading, error } = useApi(getOverview, [], 30_000)

  if (loading) return <div className="text-gray-500 text-sm">Loading overview…</div>
  if (error) return <div className="text-red-500 text-sm">Error: {error}</div>
  if (!data) return null

  const { bot_status: bs, portfolio: port, recent_signals, risk_status: rs } = data
  const pl = bs.daily_pl
  const plPositive = pl >= 0

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-gray-900">Overview</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            Last updated: {new Date(bs.last_updated).toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {bs.emergency_stopped ? (
            <Badge label="🚨 EMERGENCY STOPPED" variant="red" size="md" />
          ) : bs.running ? (
            <Badge label="🟢 BOT RUNNING" variant="green" size="md" />
          ) : (
            <Badge label="⏸ BOT PAUSED" variant="yellow" size="md" />
          )}
          {bs.paper_mode && <Badge label="📄 PAPER MODE" variant="blue" size="md" />}
          {bs.market_open ? (
            <Badge label="Market Open" variant="green" size="md" />
          ) : (
            <Badge label="Market Closed" variant="gray" size="md" />
          )}
        </div>
      </div>

      {/* Disclaimer */}
      <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-3 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-yellow-600 shrink-0 mt-0.5" />
        <p className="text-xs text-yellow-800">
          <strong>Disclaimer:</strong> This software is for research and educational purposes only.
          It is not financial advice. Paper trading is enabled by default. Real trading involves risk of loss.
        </p>
      </div>

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="Account Value"
          value={fmt(bs.account_value)}
          sub="Paper portfolio"
          icon={<DollarSign className="w-4 h-4" />}
          color="blue"
        />
        <StatCard
          label="Daily P/L"
          value={(plPositive ? '+' : '-') + fmt(Math.abs(pl))}
          sub={plPositive ? 'Profitable day' : 'Down today'}
          icon={plPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          color={plPositive ? 'green' : 'red'}
        />
        <StatCard
          label="Open Positions"
          value={`${bs.open_positions} / ${rs.max_open_positions}`}
          sub="Concurrent positions"
          icon={<BarChart2 className="w-4 h-4" />}
        />
        <StatCard
          label="Trades Today"
          value={bs.trades_today}
          sub={`${bs.signals_today} signals generated`}
          icon={<Activity className="w-4 h-4" />}
        />
      </div>

      {/* Risk bar */}
      <Card title="Daily Loss Limit Usage">
        <div className="flex items-center gap-3">
          <div className="flex-1 bg-gray-100 rounded-full h-3 overflow-hidden">
            <div
              className={`h-3 rounded-full transition-all ${
                rs.daily_loss_pct > 80 ? 'bg-red-500' :
                rs.daily_loss_pct > 50 ? 'bg-yellow-500' : 'bg-green-500'
              }`}
              style={{ width: `${Math.min(100, rs.daily_loss_pct)}%` }}
            />
          </div>
          <span className="text-sm font-medium text-gray-700 whitespace-nowrap">
            ${rs.daily_loss_usd.toFixed(2)} / ${rs.max_daily_loss_usd.toFixed(2)}
            <span className="text-gray-400 ml-1">({rs.daily_loss_pct.toFixed(0)}%)</span>
          </span>
        </div>
        {rs.risk_warnings.length > 0 && (
          <ul className="mt-2 space-y-1">
            {rs.risk_warnings.map((w, i) => (
              <li key={i} className="flex items-center gap-1.5 text-xs text-yellow-700">
                <AlertCircle className="w-3 h-3 shrink-0" />
                {w}
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* Recent signals */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card title="Recent Signals" subtitle="Latest AI-generated trading signals">
          {recent_signals.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">No signals yet</p>
          ) : (
            <div className="divide-y divide-gray-50">
              {recent_signals.slice(0, 6).map((s) => (
                <SignalRow key={s.id} s={s} />
              ))}
            </div>
          )}
        </Card>

        <Card title="Portfolio Summary" subtitle={port ? `As of ${new Date(port.snapshot_at).toLocaleTimeString()}` : 'No snapshot yet'}>
          {port ? (
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Cash Balance</span>
                <span className="font-medium">{fmt(port.cash_balance)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Positions Value</span>
                <span className="font-medium">{fmt(port.positions_value)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Unrealized P/L</span>
                <span className={`font-medium ${port.unrealized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {port.unrealized_pl >= 0 ? '+' : ''}{fmt(port.unrealized_pl)}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500">Daily P/L</span>
                <span className={`font-medium ${port.daily_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {port.daily_pl >= 0 ? '+' : ''}{fmt(port.daily_pl)}
                </span>
              </div>
              <div className="flex justify-between text-sm border-t border-gray-100 pt-2">
                <span className="font-semibold text-gray-700">Total Equity</span>
                <span className="font-bold text-blue-600">{fmt(port.account_value)}</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 py-4 text-gray-400">
              <Zap className="w-4 h-4" />
              <span className="text-sm">Portfolio snapshot loading…</span>
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
