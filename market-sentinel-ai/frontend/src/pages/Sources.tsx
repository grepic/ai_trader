import { getSources, getVerifiedEvents } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'

const actionVariant: Record<string, 'green' | 'yellow' | 'gray'> = {
  TRADE_ALLOWED: 'green',
  ALERT_ONLY: 'yellow',
  IGNORE: 'gray',
}

const sourceTypeVariant: Record<string, 'blue' | 'purple' | 'yellow' | 'gray' | 'green'> = {
  news: 'blue',
  sec: 'green',
  social: 'yellow',
  earnings: 'purple',
  price: 'gray',
}

export function Sources() {
  const { data: sources, loading: l1 } = useApi(() => getSources(100), [], 20_000)
  const { data: verified, loading: l2 } = useApi(() => getVerifiedEvents(50), [], 20_000)

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold text-gray-900">Data Sources</h1>

      {/* Verified Events */}
      <div>
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Verified Events ({verified?.length ?? 0})
        </h2>
        {l2 && <p className="text-sm text-gray-400">Loading…</p>}
        {verified && verified.length === 0 && (
          <Card>
            <p className="text-sm text-gray-400 text-center py-4">No verified events yet.</p>
          </Card>
        )}
        <div className="space-y-2">
          {verified?.map((ev) => (
            <Card key={ev.id} className="hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-sm text-gray-900">{ev.ticker}</span>
                  <Badge
                    label={ev.recommended_action.replace('_', ' ')}
                    variant={actionVariant[ev.recommended_action] ?? 'gray'}
                  />
                  <Badge label={ev.event_type.replace(/_/g, ' ')} variant="blue" />
                </div>
                <span className="text-xs text-gray-400">{new Date(ev.created_at).toLocaleTimeString()}</span>
              </div>
              <div className="mt-2 grid grid-cols-4 gap-3 text-xs">
                <div>
                  <span className="text-gray-400">Credibility</span>
                  <p className="font-semibold text-gray-700">{ev.credibility_score.toFixed(0)}</p>
                </div>
                <div>
                  <span className="text-gray-400">Corroboration</span>
                  <p className="font-semibold text-gray-700">{ev.corroboration_score.toFixed(0)}</p>
                </div>
                <div>
                  <span className="text-gray-400">Freshness</span>
                  <p className="font-semibold text-gray-700">{ev.market_reaction_score.toFixed(0)}</p>
                </div>
                <div>
                  <span className="text-gray-400">Final Conf.</span>
                  <p className={`font-bold ${ev.final_confidence_score >= 70 ? 'text-green-600' : ev.final_confidence_score >= 40 ? 'text-yellow-600' : 'text-red-600'}`}>
                    {ev.final_confidence_score.toFixed(0)}%
                  </p>
                </div>
              </div>
              {ev.verification_notes && (
                <p className="mt-1.5 text-xs text-gray-400 italic">{ev.verification_notes}</p>
              )}
            </Card>
          ))}
        </div>
      </div>

      {/* Raw sources */}
      <div>
        <h2 className="text-sm font-semibold text-gray-600 uppercase tracking-wide mb-3">
          Raw Collected Items ({sources?.length ?? 0})
        </h2>
        {l1 && <p className="text-sm text-gray-400">Loading…</p>}
        {sources && sources.length === 0 && (
          <Card>
            <p className="text-sm text-gray-400 text-center py-4">
              No source items collected yet. The bot collects data from news, SEC filings, and social media every few minutes.
            </p>
          </Card>
        )}
        <div className="space-y-2">
          {sources?.map((s) => (
            <Card key={s.id} className="hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    {s.ticker_detected && (
                      <span className="font-bold text-sm text-gray-900">{s.ticker_detected}</span>
                    )}
                    <Badge
                      label={s.source_type}
                      variant={sourceTypeVariant[s.source_type] ?? 'gray'}
                    />
                    <span className="text-xs text-gray-400">{s.source_name}</span>
                    {s.is_processed && <Badge label="✓ Processed" variant="green" />}
                  </div>
                  <p className="text-sm text-gray-700 truncate">{s.headline ?? '(no headline)'}</p>
                  {s.author && <p className="text-xs text-gray-400 mt-0.5">By {s.author}</p>}
                </div>
                <span className="text-xs text-gray-400 shrink-0 ml-3">
                  {s.published_at ? new Date(s.published_at).toLocaleTimeString() : '—'}
                </span>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
