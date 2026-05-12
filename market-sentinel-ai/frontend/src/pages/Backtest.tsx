import { useState } from 'react'
import { runBacktest } from '../api/client'
import { Card, StatCard } from '../components/ui/Card'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import type { BacktestResult } from '../types'
import { Play } from 'lucide-react'

const DEFAULT_TICKERS = ['AAPL', 'MSFT', 'NVDA']
const DEFAULT_STRATEGIES = [
  { value: 'news_momentum', label: 'News Momentum' },
  { value: 'earnings_surprise', label: 'Earnings Surprise' },
  { value: 'social_sentiment', label: 'Social Sentiment Alert-Only' },
]

export function Backtest() {
  const [tickers, setTickers] = useState(DEFAULT_TICKERS.join(','))
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [capital, setCapital] = useState(10000)
  const [strategy, setStrategy] = useState('news_momentum')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<BacktestResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    try {
      const tickerList = tickers.split(',').map((t) => t.trim().toUpperCase()).filter(Boolean)
      const r = await runBacktest({
        tickers: tickerList,
        start_date: startDate,
        end_date: endDate,
        initial_capital: capital,
        strategy,
      })
      setResult(r)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  const returnColor = result && result.total_return_pct >= 0 ? 'green' : 'red'

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-900">Backtesting</h1>

      <Card title="Backtest Configuration">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Tickers (comma separated)
            </label>
            <input
              type="text"
              value={tickers}
              onChange={(e) => setTickers(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="AAPL, MSFT, NVDA"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Start Date</label>
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">End Date</label>
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">
              Initial Capital ($)
            </label>
            <input
              type="number"
              value={capital}
              onChange={(e) => setCapital(Number(e.target.value))}
              min={100}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 mb-1">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {DEFAULT_STRATEGIES.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        <button
          onClick={handleRun}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <Play className="w-4 h-4" />
          {loading ? 'Running Backtest…' : 'Run Backtest'}
        </button>

        {error && <p className="mt-2 text-sm text-red-500">{error}</p>}
        <p className="mt-2 text-xs text-gray-400">
          Note: Uses synthetic price data for demo. Replace with real OHLCV data in production.
        </p>
      </Card>

      {result && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard
              label="Total Return"
              value={`${result.total_return_pct >= 0 ? '+' : ''}${result.total_return_pct.toFixed(2)}%`}
              sub={`$${result.initial_capital.toLocaleString()} → $${result.final_capital.toLocaleString()}`}
              color={returnColor}
            />
            <StatCard
              label="Win Rate"
              value={`${result.win_rate_pct.toFixed(1)}%`}
              sub={`${result.winning_trades}W / ${result.losing_trades}L`}
              color={result.win_rate_pct >= 50 ? 'green' : 'red'}
            />
            <StatCard
              label="Max Drawdown"
              value={`-${result.max_drawdown_pct.toFixed(2)}%`}
              color="red"
            />
            <StatCard
              label="Sharpe Ratio"
              value={result.sharpe_ratio.toFixed(2)}
              sub="Annualized"
              color={result.sharpe_ratio >= 1 ? 'green' : result.sharpe_ratio >= 0 ? 'yellow' : 'red'}
            />
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatCard label="Total Trades" value={result.total_trades} />
            <StatCard
              label="Avg Win"
              value={`$${result.avg_win.toFixed(2)}`}
              color="green"
            />
            <StatCard
              label="Avg Loss"
              value={`-$${Math.abs(result.avg_loss).toFixed(2)}`}
              color="red"
            />
            <StatCard
              label="Final Capital"
              value={`$${result.final_capital.toLocaleString()}`}
              color={returnColor}
            />
          </div>

          {result.equity_curve.length > 0 && (
            <Card title="Equity Curve">
              <ResponsiveContainer width="100%" height={280}>
                <LineChart data={result.equity_curve}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v: string) => v.slice(5)}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    tick={{ fontSize: 10 }}
                    tickFormatter={(v: number) => `$${v.toLocaleString()}`}
                  />
                  <Tooltip
                    formatter={(v: number) => [`$${v.toLocaleString()}`, 'Equity']}
                    labelFormatter={(l: string) => `Date: ${l}`}
                  />
                  <Line
                    type="monotone"
                    dataKey="equity"
                    stroke="#3b6fd4"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {(result.best_trade || result.worst_trade) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {result.best_trade && (
                <Card title="🏆 Best Trade">
                  <p className="text-lg font-bold text-green-600">+${result.best_trade.pnl.toFixed(2)}</p>
                  <p className="text-sm text-gray-600">{result.best_trade.ticker} on {result.best_trade.date}</p>
                </Card>
              )}
              {result.worst_trade && (
                <Card title="💀 Worst Trade">
                  <p className="text-lg font-bold text-red-600">${result.worst_trade.pnl.toFixed(2)}</p>
                  <p className="text-sm text-gray-600">{result.worst_trade.ticker} on {result.worst_trade.date}</p>
                </Card>
              )}
            </div>
          )}
        </>
      )}
    </div>
  )
}
