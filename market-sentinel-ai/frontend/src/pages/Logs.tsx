import { useState } from 'react'
import { getLogs } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'

const LEVEL_VARIANT: Record<string, 'green' | 'blue' | 'yellow' | 'red' | 'gray'> = {
  DEBUG: 'gray',
  INFO: 'blue',
  WARNING: 'yellow',
  ERROR: 'red',
}

export function Logs() {
  const [level, setLevel] = useState('')
  const [ticker, setTicker] = useState('')

  const fetcher = () => getLogs(200, level || undefined, undefined, ticker.toUpperCase() || undefined)
  const { data, loading, error } = useApi(fetcher, [level, ticker], 15_000)

  const logs = data ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold text-gray-900">System Logs</h1>
        <p className="text-sm text-gray-500 mt-0.5">Audit trail of all system events</p>
      </div>

      {/* Filters */}
      <Card title="Filters">
        <div className="flex flex-wrap gap-3">
          <div>
            <label className="text-xs text-gray-500 block mb-1">Level</label>
            <select
              className="text-sm border border-gray-200 rounded px-2 py-1.5 bg-white"
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            >
              <option value="">All levels</option>
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 block mb-1">Ticker</label>
            <input
              type="text"
              className="text-sm border border-gray-200 rounded px-2 py-1.5 w-24 uppercase"
              placeholder="AAPL"
              value={ticker}
              onChange={(e) => setTicker(e.target.value)}
            />
          </div>
          <div className="self-end">
            <span className="text-xs text-gray-400">{logs.length} entries</span>
          </div>
        </div>
      </Card>

      {loading && <div className="text-gray-500 text-sm">Loading…</div>}
      {error && <div className="text-red-500 text-sm">Error: {error}</div>}

      {!loading && logs.length === 0 && (
        <Card title="No Logs">
          <p className="text-sm text-gray-400 py-4 text-center">No log entries found.</p>
        </Card>
      )}

      {logs.length > 0 && (
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-4 py-2 text-xs font-medium text-gray-500 w-36">Time</th>
                  <th className="px-4 py-2 text-xs font-medium text-gray-500 w-20">Level</th>
                  <th className="px-4 py-2 text-xs font-medium text-gray-500 w-28">Component</th>
                  <th className="px-4 py-2 text-xs font-medium text-gray-500 w-16">Ticker</th>
                  <th className="px-4 py-2 text-xs font-medium text-gray-500">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {logs.map((log) => (
                  <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2 text-xs text-gray-400 font-mono whitespace-nowrap">
                      {new Date(log.created_at).toLocaleTimeString('en-US', { hour12: false })}
                    </td>
                    <td className="px-4 py-2">
                      <Badge
                        label={log.level}
                        variant={LEVEL_VARIANT[log.level] ?? 'gray'}
                      />
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-600 font-mono">{log.component}</td>
                    <td className="px-4 py-2">
                      {log.ticker && (
                        <span className="text-xs font-bold text-gray-700 bg-gray-100 px-1.5 py-0.5 rounded">
                          {log.ticker}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-xs text-gray-700">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
