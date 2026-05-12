import { getPositions, getPortfolio } from '../api/client'
import { useApi } from '../hooks/useApi'
import { Badge } from '../components/ui/Badge'
import { Card, StatCard } from '../components/ui/Card'
import { TrendingUp, TrendingDown, DollarSign, BarChart2 } from 'lucide-react'

function fmt(n: number, prefix = '$') {
  const abs = Math.abs(n)
  const s = abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return `${prefix}${s}`
}

export function Positions() {
  const { data: positions, loading } = useApi(getPositions, [], 30_000)
  const { data: portfolio } = useApi(getPortfolio, [], 30_000)

  const totalUpl = positions?.reduce((s, p) => s + p.unrealized_pl, 0) ?? 0

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold text-gray-900">Positions</h1>

      {portfolio && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Account Equity"
            value={fmt(portfolio.account_value)}
            icon={<DollarSign className="w-4 h-4" />}
            color="blue"
          />
          <StatCard
            label="Cash Available"
            value={fmt(portfolio.cash_balance)}
            sub="Buying power"
          />
          <StatCard
            label="Positions Value"
            value={fmt(portfolio.positions_value)}
            icon={<BarChart2 className="w-4 h-4" />}
          />
          <StatCard
            label="Unrealized P/L"
            value={(totalUpl >= 0 ? '+' : '') + fmt(totalUpl)}
            icon={totalUpl >= 0 ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            color={totalUpl >= 0 ? 'green' : 'red'}
          />
        </div>
      )}

      {loading && <p className="text-sm text-gray-400">Loading positions…</p>}

      {!loading && (!positions || positions.length === 0) && (
        <Card>
          <p className="text-sm text-gray-400 text-center py-8">
            No open positions. The bot will open positions when valid trade signals are generated.
          </p>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {positions?.map((pos) => {
          const isUp = pos.unrealized_pl >= 0
          return (
            <Card key={pos.id} className="hover:shadow-md transition-shadow">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <span className="text-lg font-bold text-gray-900">{pos.ticker}</span>
                  {pos.paper_mode && (
                    <Badge label="Paper" variant="blue" />
                  )}
                </div>
                <div className={`text-right ${isUp ? 'text-green-600' : 'text-red-600'}`}>
                  <p className="text-base font-bold">
                    {isUp ? '+' : ''}{fmt(pos.unrealized_pl)}
                  </p>
                  <p className="text-xs">
                    {isUp ? '+' : ''}{pos.unrealized_pl_pct.toFixed(2)}%
                  </p>
                </div>
              </div>

              <div className="space-y-1.5 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-500">Quantity</span>
                  <span className="font-medium">{pos.quantity.toFixed(4)} shares</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Avg Entry</span>
                  <span className="font-medium">{fmt(pos.avg_entry_price)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Current Price</span>
                  <span className="font-medium">{fmt(pos.current_price)}</span>
                </div>
                <div className="flex justify-between border-t border-gray-100 pt-1.5">
                  <span className="text-gray-500">Market Value</span>
                  <span className="font-bold text-gray-800">{fmt(pos.market_value)}</span>
                </div>
              </div>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
