import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity,
  AlertTriangle,
  BarChart2,
  BookOpen,
  FileText,
  LayoutDashboard,
  List,
  ScrollText,
  Settings,
  Shield,
  TrendingUp,
} from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { to: '/', label: 'Overview', icon: LayoutDashboard, end: true },
  { to: '/signals', label: 'Signals', icon: Activity },
  { to: '/trades', label: 'Trades', icon: TrendingUp },
  { to: '/positions', label: 'Positions', icon: BarChart2 },
  { to: '/sources', label: 'Sources', icon: BookOpen },
  { to: '/risk', label: 'Risk Controls', icon: Shield },
  { to: '/backtest', label: 'Backtest', icon: List },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/logs', label: 'Logs', icon: ScrollText },
  { to: '/settings', label: 'Settings', icon: Settings },
]

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Sidebar */}
      <aside className="w-56 bg-slate-900 text-white flex flex-col shrink-0">
        <div className="p-4 border-b border-slate-700">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            <div>
              <p className="text-sm font-bold leading-tight">Market Sentinel</p>
              <p className="text-xs text-slate-400">AI Trading Assistant</p>
            </div>
          </div>
          <div className="mt-2 px-2 py-1 rounded bg-yellow-500/10 border border-yellow-500/30">
            <p className="text-xs text-yellow-400 text-center font-medium">📄 PAPER MODE</p>
          </div>
        </div>

        <nav className="flex-1 py-4 space-y-0.5 px-2">
          {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors',
                  isActive
                    ? 'bg-blue-600 text-white font-medium'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800'
                )
              }
            >
              <Icon className="w-4 h-4 shrink-0" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="p-3 border-t border-slate-700">
          <p className="text-xs text-slate-500 text-center leading-snug">
            ⚠️ Research use only.<br />Not financial advice.
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
