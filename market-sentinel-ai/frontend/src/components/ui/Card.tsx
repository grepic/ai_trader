import clsx from 'clsx'
import type { ReactNode } from 'react'

interface CardProps {
  children: ReactNode
  className?: string
  title?: string
  subtitle?: string
}

export function Card({ children, className, title, subtitle }: CardProps) {
  return (
    <div className={clsx('rounded-xl bg-white shadow-sm border border-gray-100 p-4', className)}>
      {(title || subtitle) && (
        <div className="mb-3">
          {title && <h3 className="text-sm font-semibold text-gray-800">{title}</h3>}
          {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
      )}
      {children}
    </div>
  )
}

interface StatCardProps {
  label: string
  value: string | number
  sub?: string
  color?: 'default' | 'green' | 'red' | 'blue' | 'yellow'
  icon?: ReactNode
}

const colorMap = {
  default: 'text-gray-900',
  green: 'text-green-600',
  red: 'text-red-600',
  blue: 'text-blue-600',
  yellow: 'text-yellow-600',
}

export function StatCard({ label, value, sub, color = 'default', icon }: StatCardProps) {
  return (
    <div className="rounded-xl bg-white shadow-sm border border-gray-100 p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{label}</p>
        {icon && <span className="text-gray-400">{icon}</span>}
      </div>
      <p className={clsx('text-2xl font-bold', colorMap[color])}>{value}</p>
      {sub && <p className="text-xs text-gray-500">{sub}</p>}
    </div>
  )
}
