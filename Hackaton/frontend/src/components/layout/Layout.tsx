import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { useFilters } from '../../context/FiltersContext'
import { DISCLAIMER } from '../../lib/constants'
import { Notice } from '../ui/Primitives'
import { FiltersBar } from './FiltersBar'
import { MobileNav, Sidebar, Topbar } from './Sidebar'
import { Outlet } from 'react-router-dom'

export function DataModeBanner() {
  const { meta } = useFilters()
  if (meta.data_mode === 'real') return null
  if (meta.data_mode === 'sample') {
    return (
      <div className="mb-4">
        <Notice tone="warning" title="Modo muestra (datos reales, subconjunto)">
          Se está usando una muestra auténtica de NASA FIRMS para demostración offline. No representa el
          dataset completo y está claramente identificada como muestra.
        </Notice>
      </div>
    )
  }
  return (
    <div className="mb-4">
      <Notice tone="critical" title="No hay datos cargados">
        Ejecuta <code className="rounded bg-black/30 px-1">backend/.venv/bin/python scripts/ingest_firms.py</code> para
        descargar datos de NASA FIRMS o coloca una muestra en <code className="rounded bg-black/30 px-1">data/samples/</code>.
        La aplicación no inventa datos.
      </Notice>
    </div>
  )
}

export function PageHeader({
  eyebrow,
  title,
  description,
  icon: Icon,
  actions,
}: {
  eyebrow: string
  title: string
  description?: string
  icon: LucideIcon
  actions?: ReactNode
}) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
      <div className="flex items-start gap-3">
        <span className="mt-0.5 rounded-xl border border-ember-400/25 bg-ember-500/10 p-2 text-ember-300">
          <Icon size={18} strokeWidth={1.8} />
        </span>
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h2 className="mt-1 text-lg font-semibold tracking-tight text-white sm:text-xl">{title}</h2>
          {description && (
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slateish sm:text-sm">{description}</p>
          )}
        </div>
      </div>
      {actions}
    </div>
  )
}

export function Layout() {
  const { meta } = useFilters()

  return (
    <div className="min-h-screen">
      <Sidebar />
      <div className="lg:pl-64">
        <MobileNav />
        <main className="mx-auto max-w-[1600px] px-3 py-4 sm:px-5 lg:px-7">
          <Topbar meta={meta} />
          <DataModeBanner />
          <FiltersBar />
          <Outlet />
          <footer className="mt-8 border-t border-ink-700/60 pb-6 pt-4 text-[10px] leading-relaxed text-slateish">
            <p>{DISCLAIMER}</p>
          </footer>
        </main>
      </div>
    </div>
  )
}
