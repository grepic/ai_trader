import { getTrades } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'

const actionVariant: Record<string, 'green' | 'red' | 'yellow' | 'gray'> = {
  BUY: 'green', SELL: 'red', SHORT: 'red', COVER: 'yellow',
  HOLD: 'gray', ALERT_ONLY: 'yellow', IGNORED: 'gray',
}

function fmt(n: number | null) {
  if (n === null || n === undefined) return '—'
  return `$${n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function Trades() {
  const { data: all, loading: l1 } = useApi(() => getTrades(100, false), [], 15_000)
  const { data: executed } = useApi(() => getTrades(100, true), [], 15_000)

  const total = all?.length ?? 0
  const executedCount = executed?.length ?? 0
  const ignoredCount = total - executedCount

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-900">Trade Decisions</h1>

      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-center">
          <p className="text-2xl font-bold text-gray-900">{total}</p>
          <p className="text-xs text-gray-500 mt-1">Total Decisions</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-center">
          <p className="text-2xl font-bold text-green-600">{executedCount}</p>
          <p className="text-xs text-gray-500 mt-1">Executed</p>
        </div>
        <div className="bg-white rounded-xl border border-gray-100 shadow-sm p-4 text-center">
          <p className="text-2xl font-bold text-gray-400">{ignoredCount}</p>
          <p className="text-xs text-gray-500 mt-1">Ignored / Blocked</p>
        </div>
      </div>

      {l1 && <p className="text-sm text-gray-400">Loading…</p>}

      {all && all.length === 0 && (
        <Card>
          <p className="text-sm text-gray-400 text-center py-8">
            No trade decisions yet. The bot will generate decisions after analyzing signals.
          </p>
        </Card>
      )}

      <div className="space-y-3">
        {all?.map((t) => (
          <Card key={t.id} className="hover:shadow-md transition-shadow">
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="font-bold text-base text-gray-900">{t.ticker}</span>
                <Badge label={t.action} variant={actionVariant[t.action] ?? 'gray'} />
                {t.executed && <Badge label="✓ Executed" variant="green" />}
                {!t.executed && t.action !== 'IGNORED' && (
                  <Badge label="Pending" variant="yellow" />
                )}
                {t.paper_mode && <Badge label="Paper" variant="blue" />}
              </div>
              <span className="text-xs text-gray-400">{new Date(t.created_at).toLocaleString()}</span>
            </div>

            <div className="mt-3 grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
              <div>
                <p className="text-xs text-gray-400">Quantity</p>
                <p className="font-medium">{t.quantity?.toFixed(4) ?? '—'} shares</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Entry Price</p>
                <p className="font-medium">{fmt(t.target_price)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Stop Loss</p>
                <p className="font-medium text-red-600">{fmt(t.stop_loss_price)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-400">Take Profit</p>
                <p className="font-medium text-green-600">{fmt(t.take_profit_price)}</p>
              </div>
            </div>

            {t.ignored_reason && (
              <div className="mt-2 pt-2 border-t border-gray-50">
                <p className="text-xs text-gray-500">
                  <span className="font-medium text-gray-600">Blocked: </span>
                  {t.ignored_reason}
                </p>
              </div>
            )}

            {t.risk_check_notes && !t.ignored_reason && (
              <div className="mt-2 pt-2 border-t border-gray-50">
                <p className="text-xs text-gray-500">
                  <span className="font-medium text-gray-600">Risk notes: </span>
                  {t.risk_check_notes}
                </p>
              </div>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}
