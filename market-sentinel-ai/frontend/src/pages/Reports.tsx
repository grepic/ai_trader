import { getDailyReports } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'

function fmt(n: number, prefix = '$') {
  const sign = n >= 0 ? '+' : '-'
  return `${prefix !== '' ? sign : ''}${prefix}${Math.abs(n).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`
}

function pct(wins: number, total: number) {
  if (total === 0) return '—'
  return `${((wins / total) * 100).toFixed(0)}%`
}

export function Reports() {
  const { data, loading, error } = useApi(getDailyReports, [], 60_000)

  if (loading) return <div className="text-gray-500 text-sm">Loading reports…</div>
  if (error) return <div className="text-red-500 text-sm">Error: {error}</div>

  const reports = data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">Daily Reports</h1>
        <p className="text-sm text-gray-500 mt-0.5">End-of-day performance summaries</p>
      </div>

      {reports.length === 0 ? (
        <Card title="No Reports">
          <p className="text-sm text-gray-400 py-4 text-center">
            No daily reports generated yet. Reports are sent at 4:30 PM ET.
          </p>
        </Card>
      ) : (
        <div className="space-y-4">
          {reports.map((r) => {
            const plPositive = r.daily_pl >= 0
            return (
              <Card
                key={r.id}
                title={`Report: ${r.report_date}`}
                subtitle={
                  <div className="flex items-center gap-2 flex-wrap">
                    {r.paper_mode && <Badge label="Paper Mode" variant="blue" />}
                    {r.sent_telegram && <Badge label="Telegram ✓" variant="green" />}
                    {r.sent_email && <Badge label="Email ✓" variant="green" />}
                  </div>
                }
              >
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500 text-xs">Account Value</p>
                    <p className="font-bold text-gray-900">${r.account_value.toLocaleString('en-US', { maximumFractionDigits: 2 })}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Daily P/L</p>
                    <p className={`font-bold ${plPositive ? 'text-green-600' : 'text-red-600'}`}>
                      {fmt(r.daily_pl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Realized P/L</p>
                    <p className={`font-semibold ${r.realized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {fmt(r.realized_pl)}
                    </p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Unrealized P/L</p>
                    <p className={`font-semibold ${r.unrealized_pl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {fmt(r.unrealized_pl)}
                    </p>
                  </div>
                </div>

                <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4 text-sm border-t border-gray-100 pt-4">
                  <div>
                    <p className="text-gray-500 text-xs">Total Trades</p>
                    <p className="font-semibold">{r.total_trades}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Win Rate</p>
                    <p className="font-semibold">{pct(r.winning_trades, r.total_trades)}</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Signals</p>
                    <p className="font-semibold">{r.signals_generated} generated / {r.signals_traded} traded</p>
                  </div>
                  <div>
                    <p className="text-gray-500 text-xs">Risk Events</p>
                    <p className={`font-semibold ${r.risk_events_count > 0 ? 'text-yellow-600' : 'text-gray-700'}`}>
                      {r.risk_events_count}
                    </p>
                  </div>
                </div>

                {(r.best_trade_ticker || r.worst_trade_ticker) && (
                  <div className="mt-4 grid grid-cols-2 gap-4 text-sm border-t border-gray-100 pt-4">
                    {r.best_trade_ticker && (
                      <div>
                        <p className="text-gray-500 text-xs">Best Trade</p>
                        <p className="font-semibold text-green-600">
                          {r.best_trade_ticker} {r.best_trade_pl != null ? fmt(r.best_trade_pl) : ''}
                        </p>
                      </div>
                    )}
                    {r.worst_trade_ticker && (
                      <div>
                        <p className="text-gray-500 text-xs">Worst Trade</p>
                        <p className="font-semibold text-red-600">
                          {r.worst_trade_ticker} {r.worst_trade_pl != null ? fmt(r.worst_trade_pl) : ''}
                        </p>
                      </div>
                    )}
                  </div>
                )}
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
