import { CalendarRange, Filter, RotateCcw, Search } from 'lucide-react'
import type { ChangeEvent } from 'react'
import { useFilters } from '../../context/FiltersContext'
import { QUALITY_OPTIONS } from '../../lib/constants'
import { formatDate, shiftIsoDays } from '../../lib/format'
import type { Sensor } from '../../types/api'
import { Badge } from '../ui/Primitives'

const SENSOR_OPTIONS: { value: 'all' | Sensor; label: string; color?: string }[] = [
  { value: 'all', label: 'Ambos' },
  { value: 'MODIS', label: 'MODIS', color: '#FFB020' },
  { value: 'VIIRS', label: 'VIIRS', color: '#FF4D5E' },
]

const PRESETS = [
  { label: '30 d', days: 30 },
  { label: '90 d', days: 90 },
  { label: '1 año', days: 365 },
  { label: 'Todo', days: 0 },
]

const fieldClass =
  'focus-ring w-full rounded-lg border border-ink-700 bg-ink-850 px-2.5 py-2 text-xs text-slate-100 outline-none transition hover:border-ink-600'

export function FiltersBar() {
  const { meta, filters, update, reset, activeFilterCount } = useFilters()
  const maxDate = meta.date_range.end ?? undefined
  const minDate = meta.date_range.start ?? undefined

  const applyPreset = (days: number) => {
    if (!maxDate) return
    update({ end: maxDate, start: days === 0 ? (minDate ?? maxDate) : shiftIsoDays(maxDate, -(days - 1)) })
  }

  return (
    <div className="panel mb-4 p-3 sm:p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slateish">
          <Filter size={13} className="text-ember-300" />
          Filtros de análisis
          {activeFilterCount > 0 && <Badge tone="ember">{activeFilterCount}</Badge>}
        </div>
        <div className="flex items-center gap-1.5">
          {PRESETS.map((preset) => (
            <button
              key={preset.label}
              type="button"
              onClick={() => applyPreset(preset.days)}
              className="focus-ring rounded-md border border-ink-700 bg-ink-800/70 px-2 py-1 text-[10px] font-medium text-slateish transition hover:border-ember-400/40 hover:text-ember-200"
            >
              {preset.label}
            </button>
          ))}
          <button
            type="button"
            onClick={reset}
            title="Restablecer filtros"
            className="focus-ring ml-1 inline-flex items-center gap-1 rounded-md border border-ink-700 bg-ink-800/70 px-2 py-1 text-[10px] font-medium text-slateish transition hover:border-ember-400/40 hover:text-ember-200"
          >
            <RotateCcw size={11} /> Reset
          </button>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 lg:grid-cols-[1.4fr_1fr_1fr_1.1fr_1fr]">
        <label className="col-span-2 flex flex-col gap-1 lg:col-span-1">
          <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Región</span>
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
          <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Sensor</span>
          <div className="grid grid-cols-3 gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
            {SENSOR_OPTIONS.map((option) => {
              const active = filters.sensor === option.value
              return (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => update({ sensor: option.value })}
                  className={`focus-ring flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[11px] font-semibold transition ${
                    active ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                  }`}
                >
                  {option.color && <span className="h-1.5 w-1.5 rounded-full" style={{ background: option.color }} />}
                  {option.label}
                </button>
              )
            })}
          </div>
        </div>

        <label className="col-span-2 flex flex-col gap-1 lg:col-span-1">
          <span className="text-[10px] font-medium uppercase tracking-wider text-slateish">Calidad</span>
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
        <span>Cobertura del dataset: {formatDate(meta.date_range.start)} a {formatDate(meta.date_range.end)}</span>
        {filters.confidence && <span className="text-amber-200/80">Filtro de calidad activo</span>}
      </div>
    </div>
  )
}
