import { CalendarRange, Filter, MapPin, RotateCcw, Search, SlidersHorizontal } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { ChangeEvent } from 'react'
import { useFilters } from '../../context/FiltersContext'
import { QUALITY_OPTIONS } from '../../lib/constants'
import { formatDate, shiftIsoDays } from '../../lib/format'
import type { Sensor } from '../../types/api'
import { Badge } from '../ui/Primitives'

const SENSOR_OPTIONS: { value: 'all' | Sensor; label: string; desc: string; color?: string }[] = [
  { value: 'all', label: 'Ambos sensores', desc: 'MODIS + VIIRS' },
  { value: 'MODIS', label: 'MODIS', desc: '~1 km · Terra/Aqua', color: '#FFB020' },
  { value: 'VIIRS', label: 'VIIRS', desc: '~375 m · NOAA-20', color: '#FF4D5E' },
]

const PRESETS = [
  { label: '30 días', short: '30 d', days: 30, desc: 'Situación reciente' },
  { label: '90 días', short: '90 d', days: 90, desc: 'Temporada actual' },
  { label: '1 año', short: '1 año', days: 365, desc: 'Histórico 12 meses' },
  { label: 'Todo el registro', short: 'Todo', days: 0, desc: 'Dataset completo' },
]

const fieldClass =
  'focus-ring w-full rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-2 text-xs text-slate-100 outline-none transition hover:border-ink-600 focus:border-ember-400'

export function FiltersBar() {
  const { meta, filters, update, reset, activeFilterCount, viewMode, regionName } = useFilters()
  const [showCustomDates, setShowCustomDates] = useState(false)

  const isBasic = viewMode === 'basic'
  const maxDate = meta.date_range.end ?? undefined
  const minDate = meta.date_range.start ?? undefined

  const applyPreset = (days: number) => {
    if (!maxDate) return
    const newStart = days === 0 ? (minDate ?? maxDate) : shiftIsoDays(maxDate, -(days - 1))
    update({ end: maxDate, start: newStart })
  }

  // Detectar cuál preset está activo
  const activePreset = useMemo(() => {
    if (!maxDate || filters.end !== maxDate) return null
    if (filters.start === shiftIsoDays(maxDate, -29)) return 30
    if (filters.start === shiftIsoDays(maxDate, -89)) return 90
    if (filters.start === shiftIsoDays(maxDate, -364)) return 365
    if (minDate && filters.start === minDate) return 0
    return null
  }, [filters.end, filters.start, maxDate, minDate])

  return (
    <div className="panel mb-6 border border-ink-700/80 bg-ink-900/90 p-3.5 shadow-md backdrop-blur-md sm:p-4">
      {isBasic ? (
        /* ================= VISTA PÚBLICO GENERAL / CIUDADANO ================= */
        <div className="space-y-3.5">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-800/80 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-ember-400/30 bg-ember-500/10 text-ember-300">
                <SlidersHorizontal size={14} />
              </span>
              <div>
                <p className="text-xs font-bold text-white">Explorar por Territorio y Período</p>
                <p className="text-[11px] text-slateish">
                  Consulta la actividad térmica en tu provincia o ajusta el rango de tiempo
                </p>
              </div>
            </div>

            {filters.region !== 'all' && (
              <button
                type="button"
                onClick={() => update({ region: 'all' })}
                className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-1 text-xs font-medium text-slate-200 transition hover:border-ember-400/40 hover:text-white"
              >
                <RotateCcw size={12} className="text-ember-400" /> Ver todo Ecuador
              </button>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-[1.3fr_2fr]">
            {/* 1. Selector de Territorio */}
            <div className="flex flex-col gap-1.5">
              <label className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
                <MapPin size={13} className="text-ember-400" />
                <span>Provincia o Región:</span>
              </label>
              <select
                className={`${fieldClass} text-xs font-medium`}
                value={filters.region}
                onChange={(event: ChangeEvent<HTMLSelectElement>) => update({ region: event.target.value })}
              >
                <option value="all">🇪🇨 Ecuador (Todo el país)</option>
                <optgroup label="Regiones Naturales">
                  {meta.regions.map((region) => (
                    <option key={region.id} value={region.id}>
                      {region.name}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Provincias">
                  {meta.provinces
                    .slice()
                    .sort((a, b) => a.name.localeCompare(b.name, 'es'))
                    .map((province) => (
                      <option key={province.id} value={province.id}>
                        {province.name}
                      </option>
                    ))}
                </optgroup>
              </select>
            </div>

            {/* 2. Selector de Período Temporal */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-1.5 text-[11px] font-semibold text-slate-300">
                  <CalendarRange size={13} className="text-ember-400" />
                  <span>Período de tiempo:</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowCustomDates((prev) => !prev)}
                  className="text-[11px] font-medium text-ember-300 underline underline-offset-2 transition hover:text-ember-200"
                >
                  {showCustomDates ? 'Ocultar fechas exactas' : 'Elegir fechas exactas'}
                </button>
              </div>

              <div className="grid grid-cols-3 gap-1.5">
                <button
                  type="button"
                  onClick={() => {
                    applyPreset(30)
                    setShowCustomDates(false)
                  }}
                  className={`focus-ring flex flex-col items-center justify-center rounded-xl border px-2 py-1.5 text-center transition ${
                    activePreset === 30
                      ? 'border-ember-400/60 bg-ember-500/20 text-white shadow-sm ring-1 ring-ember-400/30'
                      : 'border-ink-700 bg-ink-850/80 text-slate-300 hover:border-ink-600 hover:text-white'
                  }`}
                >
                  <span className="text-xs font-bold">Últimos 30 d</span>
                  <span className="text-[10px] text-slateish">Más reciente</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    applyPreset(90)
                    setShowCustomDates(false)
                  }}
                  className={`focus-ring flex flex-col items-center justify-center rounded-xl border px-2 py-1.5 text-center transition ${
                    activePreset === 90
                      ? 'border-ember-400/60 bg-ember-500/20 text-white shadow-sm ring-1 ring-ember-400/30'
                      : 'border-ink-700 bg-ink-850/80 text-slate-300 hover:border-ink-600 hover:text-white'
                  }`}
                >
                  <span className="text-xs font-bold">Últimos 90 d</span>
                  <span className="text-[10px] text-slateish">Temporada</span>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    applyPreset(365)
                    setShowCustomDates(false)
                  }}
                  className={`focus-ring flex flex-col items-center justify-center rounded-xl border px-2 py-1.5 text-center transition ${
                    activePreset === 365
                      ? 'border-ember-400/60 bg-ember-500/20 text-white shadow-sm ring-1 ring-ember-400/30'
                      : 'border-ink-700 bg-ink-850/80 text-slate-300 hover:border-ink-600 hover:text-white'
                  }`}
                >
                  <span className="text-xs font-bold">Último año</span>
                  <span className="text-[10px] text-slateish">12 meses</span>
                </button>
              </div>
            </div>
          </div>

          {/* Drawer opcional de fechas personalizadas */}
          {showCustomDates && (
            <div className="grid grid-cols-2 gap-2.5 rounded-xl border border-ink-700/60 bg-ink-850/50 p-2.5 animate-fade-in">
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-medium text-slateish">Desde</span>
                <input
                  type="date"
                  className={fieldClass}
                  value={filters.start}
                  min={minDate}
                  max={filters.end}
                  onChange={(e) => update({ start: e.target.value })}
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-[10px] font-medium text-slateish">Hasta</span>
                <input
                  type="date"
                  className={fieldClass}
                  value={filters.end}
                  min={filters.start}
                  max={maxDate}
                  onChange={(e) => update({ end: e.target.value })}
                />
              </label>
            </div>
          )}

          {/* Estado activo en lenguaje claro */}
          <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-[11px] text-slateish">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse-soft" />
              Mostrando actividad en: <strong className="text-slate-100">{regionName}</strong> del{' '}
              <strong className="text-slate-200">{formatDate(filters.start)}</strong> al{' '}
              <strong className="text-slate-200">{formatDate(filters.end)}</strong>.
            </span>
            <span className="text-[10px] text-slate-400">
              Datos verificados por satélites NASA Terra, Aqua y NOAA-20.
            </span>
          </div>
        </div>
      ) : (
        /* ================= VISTA MODO EXPERTO / CIENTÍFICO ================= */
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-ink-800/80 pb-2">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slateish">
              <Filter size={13} className="text-ember-300" />
              Telemetría Satelital & Filtros de Calibración
              {activeFilterCount > 0 && <Badge tone="ember">{activeFilterCount}</Badge>}
            </div>
            <div className="flex items-center gap-1.5">
              {PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => applyPreset(preset.days)}
                  className={`focus-ring rounded-md border px-2 py-1 text-[10px] font-medium transition ${
                    activePreset === preset.days
                      ? 'border-ember-400/60 bg-ember-500/20 text-white font-bold ring-1 ring-ember-400/30'
                      : 'border-ink-700 bg-ink-800/70 text-slateish hover:border-ember-400/40 hover:text-ember-200'
                  }`}
                >
                  {preset.short}
                </button>
              ))}
              <button
                type="button"
                onClick={reset}
                title="Restablecer filtros a valores iniciales"
                className="focus-ring ml-1 inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-800/70 px-2 py-1 text-[10px] font-medium text-slateish transition hover:border-ember-400/40 hover:text-ember-200"
              >
                <RotateCcw size={11} /> Reset
              </button>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2 lg:grid-cols-[1.4fr_1fr_1fr_1.1fr_1fr]">
            <label className="col-span-2 flex flex-col gap-1 lg:col-span-1">
              <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Región / Provincia</span>
              <select
                className={fieldClass}
                value={filters.region}
                onChange={(event: ChangeEvent<HTMLSelectElement>) => update({ region: event.target.value })}
              >
                <option value="all">Ecuador (todo)</option>
                <optgroup label="Regiones naturales">
                  {meta.regions.map((region) => (
                    <option key={region.id} value={region.id}>
                      {region.name}
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Provincias">
                  {meta.provinces
                    .slice()
                    .sort((a, b) => a.name.localeCompare(b.name, 'es'))
                    .map((province) => (
                      <option key={province.id} value={province.id}>
                        {province.name}
                      </option>
                    ))}
                </optgroup>
              </select>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Desde</span>
              <div className="relative">
                <CalendarRange size={13} className="pointer-events-none absolute left-2.5 top-2.5 text-slateish" />
                <input
                  type="date"
                  className={`${fieldClass} pl-8`}
                  value={filters.start}
                  min={minDate}
                  max={filters.end}
                  onChange={(event) => update({ start: event.target.value })}
                />
              </div>
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Hasta</span>
              <div className="relative">
                <CalendarRange size={13} className="pointer-events-none absolute left-2.5 top-2.5 text-slateish" />
                <input
                  type="date"
                  className={`${fieldClass} pl-8`}
                  value={filters.end}
                  min={filters.start}
                  max={maxDate}
                  onChange={(event) => update({ end: event.target.value })}
                />
              </div>
            </label>

            <div className="col-span-2 flex flex-col gap-1 lg:col-span-1">
              <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Sensor orbital</span>
              <div className="grid grid-cols-3 gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
                {SENSOR_OPTIONS.map((option) => {
                  const active = filters.sensor === option.value
                  return (
                    <button
                      key={option.value}
                      type="button"
                      title={option.desc}
                      onClick={() => update({ sensor: option.value })}
                      className={`focus-ring flex items-center justify-center gap-1.5 rounded-md px-1.5 py-1.5 text-[11px] font-semibold transition ${
                        active ? 'bg-ink-700 text-white shadow-sm' : 'text-slateish hover:text-slate-200'
                      }`}
                    >
                      {option.color && (
                        <span className="h-1.5 w-1.5 rounded-full" style={{ background: option.color }} />
                      )}
                      {option.label}
                    </button>
                  )
                })}
              </div>
            </div>

            <label className="col-span-2 flex flex-col gap-1 lg:col-span-1">
              <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Calidad algorítmica</span>
              <select
                className={fieldClass}
                value={filters.confidence}
                onChange={(event) => update({ confidence: event.target.value })}
              >
                {QUALITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slateish">
            <span className="inline-flex items-center gap-1">
              <Search size={10} /> {formatDate(filters.start)} → {formatDate(filters.end)}
            </span>
            <span className="text-ink-500">·</span>
            <span>
              Dataset total: {formatDate(meta.date_range.start)} a {formatDate(meta.date_range.end)}
            </span>
            {filters.sensor !== 'all' && (
              <span className="text-sky-300 font-medium">Sensor: {filters.sensor}</span>
            )}
            {filters.confidence && (
              <span className="text-amber-200 font-medium">Filtro de confianza activo</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
