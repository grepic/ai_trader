import { useState } from 'react'
import { addTicker, getWatchlist, removeTicker } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { Plus, Trash2 } from 'lucide-react'

export function Settings() {
  const { data: watchlist, loading, refetch } = useApi(getWatchlist, [])
  const [newTicker, setNewTicker] = useState('')
  const [newName, setNewName] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [removing, setRemoving] = useState<string | null>(null)

  const handleAdd = async () => {
    if (!newTicker.trim()) return
    setError(null)
    try {
      await addTicker({ ticker: newTicker.trim().toUpperCase(), name: newName.trim() || undefined })
      setNewTicker('')
      setNewName('')
      await refetch()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to add ticker')
    }
  }

  const handleRemove = async (ticker: string) => {
    setRemoving(ticker)
    try {
      await removeTicker(ticker)
      await refetch()
    } catch {
      // ignore
    } finally {
      setRemoving(null)
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-900">Settings</h1>

      {/* Watchlist */}
      <Card title="Watchlist Tickers" subtitle="Tickers the bot monitors and may trade">
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            placeholder="Ticker (e.g. AAPL)"
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value.toUpperCase())}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg w-32 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <input
            type="text"
            placeholder="Company name (optional)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            className="px-3 py-1.5 text-sm border border-gray-200 rounded-lg flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleAdd}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
          >
            <Plus className="w-4 h-4" /> Add
          </button>
        </div>
        {error && <p className="text-xs text-red-500 mb-2">{error}</p>}

        {loading && <p className="text-sm text-gray-400">Loading…</p>}

        <div className="space-y-2">
          {watchlist?.map((w) => (
            <div
              key={w.id}
              className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0"
            >
              <div className="flex items-center gap-3">
                <span className="font-bold text-sm text-gray-900 w-16">{w.ticker}</span>
                <span className="text-sm text-gray-600">{w.name ?? '—'}</span>
                {w.sector && <Badge label={w.sector} variant="gray" />}
                {!w.is_active && <Badge label="Inactive" variant="yellow" />}
              </div>
              <button
                onClick={() => handleRemove(w.ticker)}
                disabled={removing === w.ticker}
                className="p-1.5 text-gray-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors disabled:opacity-40"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>
          ))}
          {watchlist?.length === 0 && (
            <p className="text-sm text-gray-400 text-center py-4">No tickers in watchlist</p>
          )}
        </div>
      </Card>

      {/* API Keys Status */}
      <Card title="API Keys & Integrations">
        <div className="space-y-3 text-sm">
          <p className="text-xs text-gray-400 mb-2">
            Configure API keys via <code className="bg-gray-100 px-1 py-0.5 rounded">.env</code> file.
          </p>
          {[
            { name: 'Alpaca (Broker)', env: 'ALPACA_API_KEY', description: 'Paper trading integration' },
            { name: 'OpenAI', env: 'OPENAI_API_KEY', description: 'AI analysis engine' },
            { name: 'Telegram Bot', env: 'TELEGRAM_BOT_TOKEN', description: 'Real-time notifications' },
            { name: 'Email (SMTP)', env: 'EMAIL_USERNAME', description: 'Daily report emails' },
            { name: 'NewsAPI', env: 'NEWSAPI_KEY', description: 'Financial news feed' },
            { name: 'Twitter/X', env: 'TWITTER_BEARER_TOKEN', description: 'Social sentiment' },
          ].map((item) => (
            <div key={item.name} className="flex items-center justify-between py-2 border-b border-gray-50 last:border-0">
              <div>
                <p className="font-medium text-gray-800">{item.name}</p>
                <p className="text-xs text-gray-400">{item.description}</p>
              </div>
              <code className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded font-mono">
                {item.env}
              </code>
            </div>
          ))}
        </div>
      </Card>

      {/* Safety notice */}
      <Card title="Safety Configuration">
        <div className="space-y-2 text-sm text-gray-600">
          <p>The following environment variables control real trading access (disabled by default):</p>
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 space-y-1 font-mono text-xs text-red-800">
            <p>PAPER_TRADING_ONLY=true  <span className="text-red-500"># Must be false to enable live trading</span></p>
            <p>REAL_TRADING_ENABLED=false  <span className="text-red-500"># Must be explicitly true</span></p>
          </div>
          <p className="text-xs text-red-600 font-medium">
            ⚠️ Both must be changed simultaneously to enable real trading. This is an intentional double opt-in safety mechanism.
          </p>
        </div>
      </Card>
    </div>
  )
}
