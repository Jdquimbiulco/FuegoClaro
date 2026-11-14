import type { LucideIcon } from 'lucide-react'
import { AlertTriangle, Inbox, LoaderCircle, RefreshCw } from 'lucide-react'
import type { ReactNode } from 'react'

export function Card({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <section className={`panel p-4 sm:p-5 ${className}`}>{children}</section>
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        {eyebrow && <p className="eyebrow mb-1">{eyebrow}</p>}
        <h2 className="text-base font-semibold text-white sm:text-lg">{title}</h2>
        {description && <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slateish sm:text-sm">{description}</p>}
      </div>
      {action}
    </div>
  )
}

const BADGE_STYLES: Record<string, string> = {
  info: 'border-sky-400/25 bg-sky-400/10 text-sky-200',
  warning: 'border-amber-400/30 bg-amber-400/10 text-amber-200',
  critical: 'border-rose-400/30 bg-rose-400/10 text-rose-200',
  positive: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-200',
  neutral: 'border-ink-600 bg-ink-800 text-slateish',
  ember: 'border-ember-400/35 bg-ember-500/10 text-ember-200',
}

export function Badge({
  children,
  tone = 'neutral',
  className = '',
}: {
  children: ReactNode
  tone?: keyof typeof BADGE_STYLES
  className?: string
}) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider ${BADGE_STYLES[tone] ?? BADGE_STYLES.neutral} ${className}`}>
      {children}
    </span>
  )
}

export function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  accent = '#FF5C16',
  loading = false,
}: {
  label: string
  value: ReactNode
  sub?: ReactNode
  icon: LucideIcon
  accent?: string
  loading?: boolean
}) {
  return (
    <div className="panel group relative overflow-hidden p-4 transition hover:border-ink-600">
      <div
        className="pointer-events-none absolute -right-8 -top-8 h-24 w-24 rounded-full opacity-20 blur-2xl transition group-hover:opacity-35"
        style={{ background: accent }}
      />
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slateish">{label}</p>
        <span className="rounded-lg border border-ink-700 bg-ink-800/80 p-1.5" style={{ color: accent }}>
          <Icon size={15} strokeWidth={1.8} />
        </span>
      </div>
      <p className="num mt-3 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
        {loading ? <span className="inline-block h-8 w-24 animate-pulse rounded bg-ink-700" /> : value}
      </p>
      {sub && <p className="mt-1.5 text-xs leading-relaxed text-slateish">{sub}</p>}
    </div>
  )
}

export function SensorDot({ sensor }: { sensor: 'MODIS' | 'VIIRS' }) {
  return (
    <span
      className="inline-block h-2 w-2 rounded-full"
      style={{ background: sensor === 'MODIS' ? '#FFB020' : '#FF4D5E' }}
    />
  )
}

export function Notice({
  tone = 'info',
  title,
  children,
  icon: Icon = AlertTriangle,
}: {
  tone?: 'info' | 'warning' | 'critical' | 'neutral'
  title?: string
  children: ReactNode
  icon?: LucideIcon
}) {
  const styles = {
    info: 'border-sky-400/20 bg-sky-400/5 text-sky-100',
    warning: 'border-amber-400/25 bg-amber-400/5 text-amber-100',
    critical: 'border-rose-400/25 bg-rose-400/5 text-rose-100',
    neutral: 'border-ink-700 bg-ink-800/60 text-slate-200',
  }
  return (
    <div className={`flex gap-3 rounded-xl border p-3 text-xs leading-relaxed ${styles[tone]}`}>
      <Icon size={16} className="mt-0.5 shrink-0 opacity-80" />
      <div>
        {title && <p className="mb-1 font-semibold">{title}</p>}
        <div className="opacity-90">{children}</div>
      </div>
    </div>
  )
}

export function LoadingBlock({ label = 'Cargando datos…', compact = false }: { label?: string; compact?: boolean }) {
  return (
    <div className={`flex items-center justify-center gap-3 text-sm text-slateish ${compact ? 'py-6' : 'py-16'}`}>
      <LoaderCircle size={18} className="animate-spin text-ember-400" />
      {label}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="panel flex flex-col items-center gap-3 p-8 text-center">
      <span className="rounded-full border border-rose-400/25 bg-rose-400/10 p-2 text-rose-300">
        <AlertTriangle size={20} />
      </span>
      <div>
        <p className="text-sm font-semibold text-white">No se pudieron cargar los datos</p>
        <p className="mt-1 max-w-xl text-xs leading-relaxed text-slateish">{message}</p>
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ink-600 bg-ink-800 px-3 py-1.5 text-xs font-semibold text-white transition hover:border-ember-400/50 hover:text-ember-200"
        >
          <RefreshCw size={13} /> Reintentar
        </button>
      )}
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center gap-2 py-12 text-center">
      <span className="rounded-full border border-ink-600 bg-ink-800 p-2 text-slateish">
        <Inbox size={18} />
      </span>
      <p className="text-sm font-semibold text-slate-200">{title}</p>
      {description && <p className="max-w-md text-xs leading-relaxed text-slateish">{description}</p>}
    </div>
  )
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <span className={`inline-block animate-pulse rounded bg-ink-700 ${className}`} />
}
