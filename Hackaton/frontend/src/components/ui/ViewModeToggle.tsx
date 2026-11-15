import { Gauge, Users } from 'lucide-react'
import { useFilters } from '../../context/FiltersContext'

export function ViewModeToggle({ compact = false }: { compact?: boolean }) {
  const { viewMode, setViewMode } = useFilters()
  const isExpert = viewMode === 'expert'

  return (
    <div className="flex items-center gap-2.5">
      {!compact && (
        <span className="hidden text-[10px] font-bold uppercase tracking-[0.18em] text-slateish/80 xl:inline select-none">
          Perfil:
        </span>
      )}
      <div className="relative inline-flex items-center rounded-xl border border-ink-600/90 bg-ink-950/95 p-1 shadow-lg shadow-black/50 backdrop-blur-md select-none">
        {/* Pastilla deslizante animada (GPU accelerated) */}
        <div className="absolute inset-1 grid grid-cols-2 pointer-events-none">
          <div
            className={`h-full w-full rounded-lg transition-transform duration-300 ease-[cubic-bezier(0.2,0.8,0.2,1)] ${
              isExpert
                ? 'translate-x-full bg-gradient-to-r from-sky-500/25 via-sky-400/20 to-cyan-500/25 border border-sky-400/70 shadow-[0_0_18px_rgba(56,189,248,0.4)]'
                : 'translate-x-0 bg-gradient-to-r from-ember-500/30 via-ember-400/25 to-amber-500/20 border border-ember-400/70 shadow-[0_0_18px_rgba(255,92,22,0.4)]'
            }`}
          />
        </div>

        {/* Botón 1: Público General */}
        <button
          type="button"
          onClick={() => setViewMode('basic')}
          className={`relative z-10 flex items-center justify-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-colors duration-200 focus:outline-none ${
            !isExpert ? 'text-ember-200' : 'text-slateish hover:text-slate-100'
          }`}
          title="Vista limpia e intuitiva para público general y tomadores de decisiones"
        >
          <Users
            size={14}
            className={`transition-all duration-200 ${
              !isExpert ? 'scale-110 text-ember-300 drop-shadow-[0_0_8px_rgba(255,92,22,0.6)]' : 'text-slateish'
            }`}
          />
          <span className="tracking-tight">Público General</span>
          <span
            className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
              !isExpert
                ? 'bg-ember-400 scale-100 opacity-100 shadow-[0_0_6px_rgba(255,92,22,0.8)]'
                : 'scale-0 opacity-0'
            }`}
          />
        </button>

        {/* Botón 2: Modo Experto */}
        <button
          type="button"
          onClick={() => setViewMode('expert')}
          className={`relative z-10 flex items-center justify-center gap-2 rounded-lg px-3.5 py-1.5 text-xs font-bold transition-colors duration-200 focus:outline-none ${
            isExpert ? 'text-sky-200' : 'text-slateish hover:text-slate-100'
          }`}
          title="Vista analítica con telemetría de satélites, calibración FRP y métricas científicas"
        >
          <Gauge
            size={14}
            className={`transition-all duration-200 ${
              isExpert ? 'scale-110 text-sky-300 drop-shadow-[0_0_8px_rgba(56,189,248,0.6)]' : 'text-slateish'
            }`}
          />
          <span className="tracking-tight">Modo Experto</span>
          <span
            className={`h-1.5 w-1.5 rounded-full transition-all duration-300 ${
              isExpert
                ? 'bg-sky-400 scale-100 opacity-100 shadow-[0_0_6px_rgba(56,189,248,0.8)]'
                : 'scale-0 opacity-0'
            }`}
          />
        </button>
      </div>
    </div>
  )
}
