import { useState } from 'react'
import { getSignals } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'

const sentimentVariant = {
  positive: 'green',
  negative: 'red',
  neutral: 'gray',
  mixed: 'yellow',
} as const

const decisionVariant: Record<string, 'green' | 'red' | 'yellow' | 'gray' | 'blue'> = {
  BUY: 'green', SELL: 'red', SHORT: 'red', COVER: 'yellow',
  HOLD: 'gray', ALERT_ONLY: 'yellow', IGNORE: 'gray',
}

const riskVariant: Record<string, 'green' | 'yellow' | 'red' | 'gray'> = {
  low: 'green', medium: 'yellow', high: 'red', extreme: 'red',
}

export function Signals() {
  const [ticker, setTicker] = useState('')
  const { data, loading, error } = useApi(
    () => getSignals(100, ticker || undefined),
    [ticker],
    15_000
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold text-gray-900">AI Signals</h1>
        <input
          type="text"
          placeholder="Filter by ticker…"
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg w-40 focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
      </div>

      {loading && <p className="text-sm text-gray-400">Loading signals…</p>}
      {error && <p className="text-sm text-red-500">Error: {error}</p>}

      {data && data.length === 0 && (
        <Card>
          <p className="text-sm text-gray-400 text-center py-8">
            No signals generated yet. The bot will analyze market events and generate signals automatically.
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {data?.map((s) => (
          <Card key={s.id} className="hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 flex-1 min-w-0">
                <div>
                  <span className="font-bold text-lg text-gray-900">{s.ticker}</span>
                  <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                    <Badge label={s.trade_decision} variant={decisionVariant[s.trade_decision] ?? 'gray'} />
                    <Badge label={s.sentiment} variant={sentimentVariant[s.sentiment] ?? 'gray'} />
                    <Badge label={`Risk: ${s.risk_level}`} variant={riskVariant[s.risk_level] ?? 'gray'} />
                    <Badge label={s.event_type.replace(/_/g, ' ')} variant="blue" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{s.event_summary}</p>
                  <p className="text-xs text-gray-500 mt-1 line-clamp-2">{s.reasoning_summary}</p>
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-lg font-bold text-blue-600">{s.confidence.toFixed(0)}%</div>
                <div className="text-xs text-gray-400">confidence</div>
                <div className="text-xs text-gray-400 mt-1">{s.expected_time_horizon}</div>
              </div>
            </div>
            <div className="mt-2 pt-2 border-t border-gray-50 flex items-center justify-between">
              <div className="flex items-center gap-2">
                {s.sources_used && (
                  <span className="text-xs text-gray-400">
                    Sources: {s.sources_used.join(', ')}
                  </span>
                )}
              </div>
              <span className="text-xs text-gray-400">
                {new Date(s.created_at).toLocaleString()}
              </span>
            </div>
          </Card>
        ))}
      </div>
    </div>
  )
}
