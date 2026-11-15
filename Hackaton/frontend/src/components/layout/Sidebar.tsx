import {
  BookOpen,
  CalendarDays,
  Flame,
  GitCompareArrows,
  LayoutDashboard,
  Map as MapIcon,
  Radar,
  ShieldAlert,
  Sparkles,
} from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { useFilters } from '../../context/FiltersContext'
import { formatDate } from '../../lib/format'
import { Badge } from '../ui/Primitives'
import { ViewModeToggle } from '../ui/ViewModeToggle'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/incendios', label: 'Incendios', icon: ShieldAlert },
  { to: '/mapa', label: 'Mapa', icon: MapIcon },
  { to: '/calendario', label: 'Calendario', icon: CalendarDays },
  { to: '/comparador', label: 'Comparador', icon: GitCompareArrows },
  { to: '/anomalias', label: 'Anomalías', icon: Radar },
  { to: '/hallazgos', label: 'Hallazgos', icon: Sparkles },
  { to: '/metodologia', label: 'Metodología', icon: BookOpen },
]

export function Sidebar() {
  const { meta } = useFilters()

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-ink-700/70 bg-ink-900/80 backdrop-blur-xl lg:flex">
      <div className="flex items-center gap-3 px-5 pb-5 pt-6">
        <span className="relative flex h-10 w-10 items-center justify-center rounded-xl border border-ember-400/30 bg-ember-500/10 text-ember-300 shadow-ember">
          <Flame size={20} strokeWidth={1.8} />
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 animate-pulse-soft rounded-full bg-ember-400" />
        </span>
        <div>
          <p className="text-base font-semibold tracking-tight text-white">FuegoClaro</p>
          <p className="text-[10px] uppercase tracking-[0.16em] text-slateish">NASA Space Apps 2026</p>
        </div>
      </div>

      <nav className="flex-1 space-y-1 px-3">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `focus-ring group flex items-center gap-3 rounded-lg border px-3 py-2.5 text-sm transition ${
                isActive
                  ? 'border-ember-400/25 bg-ember-500/10 text-white'
                  : 'border-transparent text-slateish hover:border-ink-700 hover:bg-ink-800/70 hover:text-slate-100'
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon size={17} strokeWidth={isActive ? 2 : 1.7} className={isActive ? 'text-ember-300' : ''} />
                <span className="font-medium">{label}</span>
                {isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-ember-400" />}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="m-3 rounded-xl border border-ink-700/70 bg-ink-850/80 p-3">
        <div className="mb-2 flex items-center justify-between">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slateish">Dataset</p>
          <Badge tone={meta.data_mode === 'real' ? 'positive' : meta.data_mode === 'sample' ? 'warning' : 'critical'}>
            {meta.data_mode === 'real' ? 'Real' : meta.data_mode === 'sample' ? 'Muestra' : 'Sin datos'}
          </Badge>
        </div>
        <p className="text-xs text-slate-200">
          {formatDate(meta.date_range.start)} — {formatDate(meta.date_range.end)}
        </p>
        <p className="mt-1 text-[10px] leading-relaxed text-slateish">
          {meta.dataset_version ?? 'Sin versión'} · NASA FIRMS
        </p>
      </div>
    </aside>
  )
}

export function MobileNav() {
  return (
    <div className="lg:hidden">
      <div className="flex items-center justify-between border-b border-ink-700/70 bg-ink-900/80 px-4 py-2.5 backdrop-blur-xl">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-ember-400/30 bg-ember-500/10 text-ember-300">
            <Flame size={16} />
          </span>
          <div>
            <p className="text-sm font-semibold text-white">FuegoClaro</p>
            <p className="text-[9px] uppercase tracking-[0.14em] text-slateish">NASA Space Apps 2026</p>
          </div>
        </div>
        <ViewModeToggle compact />
      </div>
      <nav className="flex gap-1 overflow-x-auto border-b border-ink-700/60 bg-ink-900/60 px-2 py-1.5">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium transition ${
                isActive ? 'bg-ember-500/15 text-ember-200' : 'text-slateish hover:bg-ink-800 hover:text-white'
              }`
            }
          >
            <Icon size={13} />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}

export function Topbar({ meta }: { meta: ReturnType<typeof useFilters>['meta'] }) {
  const { regionName } = useFilters()
  const live = meta.data_mode === 'real'
  return (
    <header className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-ink-800/80 pb-3">
      <div className="flex items-center gap-2.5 text-xs text-slateish">
        <span className="font-semibold text-white">FuegoClaro</span>
        <span className="text-ink-600">/</span>
        <span className="text-slate-300 font-medium">Monitoreo Satelital Ecuador</span>
        {regionName !== 'Ecuador' && (
          <>
            <span className="text-ink-600">/</span>
            <span className="rounded-md border border-ember-400/30 bg-ember-500/15 px-2 py-0.5 text-[11px] font-bold text-ember-300">
              {regionName}
            </span>
          </>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        {/* Selector de Modo con alta visibilidad */}
        <ViewModeToggle />

        <div className="flex items-center gap-2 rounded-full border border-ink-700 bg-ink-850/80 px-3 py-1 text-[11px] text-slateish">
          <span className={`h-2 w-2 rounded-full ${live ? 'bg-mint' : 'bg-amber-400'}`} />
          <span>{live ? 'NASA FIRMS' : 'Modo muestra'}</span>
          <span className="text-ink-500">|</span>
          <span className="num text-[10px] text-slate-300">{meta.dataset_version ?? '—'}</span>
        </div>
      </div>
    </header>
  )
}
