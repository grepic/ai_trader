import { useState } from 'react'
import { emergencyStop, getRiskStatus, pauseBot, resumeBot } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { AlertTriangle, CheckCircle, Pause, Play, StopCircle } from 'lucide-react'

export function RiskControls() {
  const { data, loading, refetch } = useApi(getRiskStatus, [], 10_000)
  const [actionLoading, setActionLoading] = useState(false)
  const [actionMsg, setActionMsg] = useState<string | null>(null)

  const doAction = async (fn: () => Promise<{ status: string; message?: string }>) => {
    setActionLoading(true)
    setActionMsg(null)
    try {
      const r = await fn()
      setActionMsg(r.message ?? r.status)
      await refetch()
    } catch (e) {
      setActionMsg(`Error: ${e instanceof Error ? e.message : 'Unknown'}`)
    } finally {
      setActionLoading(false)
    }
  }

  const doEmergencyStop = async () => {
    if (!confirm('⚠️ This will IMMEDIATELY stop all trading and close all open positions. Continue?')) return
    setActionLoading(true)
    setActionMsg(null)
    try {
      const r = await emergencyStop()
      setActionMsg(`Emergency stop activated. Closed: ${r.positions_closed.join(', ') || 'none'}`)
      await refetch()
    } catch (e) {
      setActionMsg(`Error: ${e instanceof Error ? e.message : 'Unknown'}`)
    } finally {
      setActionLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Risk Controls</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage bot operation. In paper mode — no real money at risk.
        </p>
      </div>

      <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-3 flex items-start gap-2">
        <AlertTriangle className="w-4 h-4 text-yellow-600 shrink-0 mt-0.5" />
        <p className="text-xs text-yellow-800">
          <strong>Paper Trading Mode Active.</strong> All trades are simulated.
          Real trading requires explicit environment variable configuration and is disabled by default.
        </p>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading risk status…</p>}

      {data && (
        <>
          {/* Status */}
          <Card title="Bot Status">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
              <div>
                <p className="text-xs text-gray-400 mb-1">Bot Status</p>
                {data.emergency_stopped ? (
                  <Badge label="🚨 Emergency Stopped" variant="red" size="md" />
                ) : data.bot_running ? (
                  <Badge label="🟢 Running" variant="green" size="md" />
                ) : (
                  <Badge label="⏸ Paused" variant="yellow" size="md" />
                )}
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Trading Mode</p>
                <Badge label={data.paper_mode ? '📄 Paper' : '💰 Live'} variant={data.paper_mode ? 'blue' : 'red'} size="md" />
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Market</p>
                <Badge label={data.market_open ? '🟢 Open' : '🔴 Closed'} variant={data.market_open ? 'green' : 'gray'} size="md" />
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Trading Allowed</p>
                {data.trading_allowed ? (
                  <div className="flex items-center gap-1 text-green-600 text-sm font-medium">
                    <CheckCircle className="w-4 h-4" /> Yes
                  </div>
                ) : (
                  <div className="flex items-center gap-1 text-red-500 text-sm font-medium">
                    <StopCircle className="w-4 h-4" /> No
                  </div>
                )}
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Open Positions</p>
                <p className="text-sm font-medium">{data.open_positions} / {data.max_open_positions}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Trades Today</p>
                <p className="text-sm font-medium">{data.trades_today}</p>
              </div>
            </div>

            {/* Daily loss bar */}
            <div className="mt-4">
              <div className="flex justify-between text-xs text-gray-500 mb-1">
                <span>Daily Loss Limit</span>
                <span>${data.daily_loss_usd.toFixed(2)} / ${data.max_daily_loss_usd.toFixed(2)} ({data.daily_loss_pct.toFixed(0)}%)</span>
              </div>
              <div className="bg-gray-100 rounded-full h-2.5 overflow-hidden">
                <div
                  className={`h-2.5 rounded-full ${data.daily_loss_pct > 80 ? 'bg-red-500' : data.daily_loss_pct > 50 ? 'bg-yellow-500' : 'bg-green-500'}`}
                  style={{ width: `${Math.min(100, data.daily_loss_pct)}%` }}
                />
              </div>
            </div>

            {data.risk_warnings.length > 0 && (
              <ul className="mt-3 space-y-1">
                {data.risk_warnings.map((w, i) => (
                  <li key={i} className="flex items-center gap-1.5 text-xs text-yellow-700">
                    <AlertTriangle className="w-3 h-3" /> {w}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* Controls */}
          <Card title="Bot Controls">
            <div className="flex flex-wrap gap-3">
              <button
                onClick={() => doAction(pauseBot)}
                disabled={actionLoading || !data.bot_running || data.emergency_stopped}
                className="flex items-center gap-2 px-4 py-2 bg-yellow-500 text-white rounded-lg text-sm font-medium hover:bg-yellow-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Pause className="w-4 h-4" /> Pause Bot
              </button>
              <button
                onClick={() => doAction(resumeBot)}
                disabled={actionLoading || data.bot_running || data.emergency_stopped}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <Play className="w-4 h-4" /> Resume Bot
              </button>
              <button
                onClick={doEmergencyStop}
                disabled={actionLoading || data.emergency_stopped}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-lg text-sm font-medium hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
              >
                <StopCircle className="w-4 h-4" /> Emergency Stop
              </button>
            </div>

            {actionMsg && (
              <div className="mt-3 p-2 rounded bg-gray-50 border border-gray-200">
                <p className="text-sm text-gray-700">{actionMsg}</p>
              </div>
            )}
          </Card>

          {/* Risk parameters (read-only view) */}
          <Card title="Risk Parameters" subtitle="Configured via environment variables">
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-sm">
              {[
                { label: 'Max Daily Loss', value: `$${data.max_daily_loss_usd}` },
                { label: 'Max Open Positions', value: data.max_open_positions },
                { label: 'Paper Mode', value: data.paper_mode ? 'Yes' : 'No' },
              ].map(({ label, value }) => (
                <div key={label} className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400">{label}</p>
                  <p className="font-semibold text-gray-800">{value}</p>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-gray-400">
              To change risk limits, update environment variables in .env and restart the service.
              Real trading requires <code className="bg-gray-100 px-1 py-0.5 rounded">REAL_TRADING_ENABLED=true</code> AND <code className="bg-gray-100 px-1 py-0.5 rounded">PAPER_TRADING_ONLY=false</code>.
            </p>
          </Card>
        </>
      )}
    </div>
  )
}
