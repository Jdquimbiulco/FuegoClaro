import {
  ArrowDownRight,
  ArrowUpRight,
  ChevronDown,
  Search,
  SlidersHorizontal,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { AnomalyBars } from '../charts/Charts'
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  SectionHeading,
} from '../ui/Primitives'
import { useFilters } from '../../context/FiltersContext'
import { useApi } from '../../hooks/useApi'
import { SENSOR_COLORS } from '../../lib/constants'
import { formatDate, formatDecimal, formatNumber } from '../../lib/format'
import type { AnomaliesData, Anomaly, ApiEnvelope } from '../../types/api'

const THRESHOLDS = [2.0, 2.5, 3.0, 3.5]
const WINDOWS = [0, 3, 7, 14]
const MIN_OBSERVED = [1, 3, 5, 10]
const FDR_LEVELS = [0.05, 0.1]

type Direction = 'all' | 'high' | 'low'

const PAGE_SIZE = 10

function normalizeText(value: string): string {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
}

function AnomalyRow({ anomaly, compact = false }: { anomaly: Anomaly; compact?: boolean }) {
  const high = anomaly.direction === 'high'
  return (
    <div className="rounded-lg border border-ink-700/60 bg-ink-850/45 p-2.5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <span
            className={`mt-0.5 rounded-lg border p-1.5 ${
              high
                ? 'border-rose-400/30 bg-rose-400/10 text-rose-300'
                : 'border-sky-400/30 bg-sky-400/10 text-sky-300'
            }`}
          >
            {high ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
          </span>
          <div>
            <p className="text-xs font-semibold text-white">
              {formatDate(anomaly.date)} · {anomaly.region}
            </p>
            <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-slateish">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: SENSOR_COLORS[anomaly.sensor] }}
              />
              {anomaly.sensor} · {anomaly.direction === 'high' ? 'por encima' : 'por debajo'} de la referencia
            </p>
          </div>
        </div>
        <div className="text-right">
          <p className="num text-sm font-semibold text-white">
            {formatNumber(anomaly.observed)} <span className="text-[10px] text-slateish">obs.</span>
          </p>
          {compact ? (
            <p className="num text-[10px] text-slateish">
              z {formatDecimal(anomaly.z_score, 2)} · base {formatDecimal(anomaly.baseline_mean, 1)}
            </p>
          ) : (
            <p className="num text-[10px] text-slateish">
              base {formatDecimal(anomaly.baseline_mean, 1)} ± {formatDecimal(anomaly.baseline_std, 1)}
            </p>
          )}
        </div>
      </div>

      {!compact && (
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-ink-700/50 pt-1.5 text-[10px] text-slateish">
          <span>
            z{' '}
            <span className={`num font-semibold ${high ? 'text-rose-200' : 'text-sky-200'}`}>
              {formatDecimal(anomaly.z_score, 2)}
            </span>
          </span>
          <span className="text-ink-600">·</span>
          <span>
            q <span className="num font-semibold text-slate-100">{anomaly.q_value.toExponential(2)}</span>
          </span>
          <span className="text-ink-600">·</span>
          <span>
            base <span className="num font-semibold text-slate-100">{formatNumber(anomaly.baseline_days)} d</span>
            {' / '}
            <span className="num font-semibold text-slate-100">{anomaly.baseline_years.join(', ') || '—'}</span>
          </span>
        </div>
      )}
    </div>
  )
}

export function AnomaliesSection() {
  const { apiPath, viewMode } = useFilters()
  const [threshold, setThreshold] = useState(2.5)
  const [windowDays, setWindowDays] = useState(7)
  const [minObserved, setMinObserved] = useState(3)
  const [fdrAlpha, setFdrAlpha] = useState(0.05)
  const [direction, setDirection] = useState<Direction>('all')
  const [regionQuery, setRegionQuery] = useState('')
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const isBasic = viewMode === 'basic'

  const anomaliesState = useApi<ApiEnvelope<AnomaliesData>>(
    apiPath('/anomalies', {
      threshold,
      window_days: windowDays,
      min_observed: minObserved,
      fdr_alpha: fdrAlpha,
      max_results: 100,
    }),
  )
  const data = anomaliesState.data?.data

  const regionNames = useMemo(
    () =>
      Array.from(new Set((data?.anomalies ?? []).map((item) => item.region))).sort((a, b) =>
        a.localeCompare(b, 'es'),
      ),
    [data],
  )

  const filtered = useMemo(() => {
    if (!data) return []
    const query = normalizeText(regionQuery.trim())
    return data.anomalies.filter((item) => {
      if (direction !== 'all' && item.direction !== direction) return false
      return !query || normalizeText(item.region).includes(query)
    })
  }, [data, direction, regionQuery])

  const visible = filtered.slice(0, visibleCount)

  const handleDirection = (nextDirection: Direction) => {
    setDirection(nextDirection)
    setVisibleCount(PAGE_SIZE)
  }

  const handleRegionQuery = (value: string) => {
    setRegionQuery(value)
    setVisibleCount(PAGE_SIZE)
  }

  return (
    <>
      {!isBasic && (
        <Card className="mb-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="rounded-lg border border-ember-400/25 bg-ember-500/10 p-1.5 text-ember-300">
              <SlidersHorizontal size={14} />
            </span>
            <div>
              <p className="text-xs font-semibold text-white">Parámetros del detector</p>
              <p className="text-[10px] text-slateish">
                Cambiar parámetros recalcula las pruebas sobre el histórico disponible.
              </p>
            </div>
          </div>
          <Badge tone="warning">No causal</Badge>
        </div>

        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slateish">
              Umbral |z|
            </p>
            <div className="flex gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
              {THRESHOLDS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setThreshold(value)}
                  className={`focus-ring flex-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
                    threshold === value ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                  }`}
                >
                  {value.toFixed(1)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slateish">
              Ventana de línea base
            </p>
            <div className="flex gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
              {WINDOWS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setWindowDays(value)}
                  className={`focus-ring flex-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
                    windowDays === value ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                  }`}
                >
                  ±{value}d
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slateish">
              Mínimo observado
            </p>
            <div className="flex gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
              {MIN_OBSERVED.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setMinObserved(value)}
                  className={`focus-ring flex-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
                    minObserved === value ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                  }`}
                >
                  {value}
                </button>
              ))}
            </div>
          </div>

          <div>
            <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-slateish">
              Control FDR (α)
            </p>
            <div className="flex gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
              {FDR_LEVELS.map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setFdrAlpha(value)}
                  className={`focus-ring flex-1 rounded-md px-2 py-1 text-[11px] font-semibold transition ${
                    fdrAlpha === value ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                  }`}
                >
                  {value.toFixed(2)}
                </button>
              ))}
            </div>
          </div>
        </div>
        </Card>
      )}

      {anomaliesState.error ? (
        <ErrorState message={anomaliesState.error} onRetry={anomaliesState.refetch} />
      ) : anomaliesState.loading && !data ? (
        <LoadingBlock label="Calculando anomalías sobre el histórico…" />
      ) : !data ? (
        <Card>
          <EmptyState title="Sin resultados de anomalías" />
        </Card>
      ) : (
        <>
          <div className={isBasic ? '' : 'grid gap-4 xl:grid-cols-[1.3fr_1fr]'}>
            <Card>
              <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">Anomalías</p>
                  <h3 className="mt-0.5 text-sm font-semibold text-white">Observado vs referencia histórica</h3>
                  <p className="mt-0.5 text-[10px] text-slateish">
                    {isBasic
                      ? 'Barra clara = observado. Oscura = histórico.'
                      : 'Mayor |z|. Claro = observado; oscuro = media histórica.'}
                  </p>
                  {isBasic && (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <Badge tone="neutral">|z| ≥ {threshold.toFixed(1)}</Badge>
                      <Badge tone="neutral">±{windowDays} d</Badge>
                      <Badge tone="neutral">mín {minObserved}</Badge>
                      <Badge tone="neutral">FDR {fdrAlpha.toFixed(2)}</Badge>
                    </div>
                  )}
                </div>
                <dl className="flex flex-wrap items-end gap-4">
                  <div className="text-right">
                    <dt className="text-[9px] uppercase tracking-wider text-slateish">Días</dt>
                    <dd className="num text-xl font-semibold text-white">{formatNumber(data.summary.flagged)}</dd>
                  </div>
                  <div className="text-right">
                    <dt className="text-[9px] uppercase tracking-wider text-slateish">Altas</dt>
                    <dd className="num text-xl font-semibold text-rose-300">{formatNumber(data.summary.high_anomalies)}</dd>
                  </div>
                  <div className="text-right">
                    <dt className="text-[9px] uppercase tracking-wider text-slateish">Bajas</dt>
                    <dd className="num text-xl font-semibold text-sky-300">{formatNumber(data.summary.low_anomalies)}</dd>
                  </div>
                  {!isBasic && (
                    <div className="text-right">
                      <dt className="text-[9px] uppercase tracking-wider text-slateish">|z| máx</dt>
                      <dd className="num text-xl font-semibold text-emerald-300">
                        {data.summary.max_abs_z !== null ? formatDecimal(data.summary.max_abs_z, 2) : '—'}
                      </dd>
                    </div>
                  )}
                </dl>
              </div>
              {data.anomalies.length === 0 ? (
                <EmptyState
                  title="Ningún día superó todos los criterios"
                  description="Con los parámetros actuales no hay días que cumplan simultáneamente el umbral de z, el mínimo observado y el control FDR. Esto no descarta eventos."
                />
              ) : (
                <AnomalyBars anomalies={data.anomalies} />
              )}
            </Card>

            {!isBasic && (
              <Card>
                <SectionHeading
                  eyebrow="Método"
                  title="Cómo se calcula"
                  description="Parámetros efectivos del detector."
                />
                <dl className="space-y-2 text-[11px]">
                  <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                    <dt className="text-slateish">Periodo analizado</dt>
                    <dd className="num text-right text-slate-100">
                      {data.analysis_period.start} → {data.analysis_period.end}
                    </dd>
                  </div>
                  <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                    <dt className="text-slateish">Ventana de comparación</dt>
                    <dd className="num text-right text-slate-100">±{windowDays} días</dd>
                  </div>
                  <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                    <dt className="text-slateish">Mínimo de detecciones</dt>
                    <dd className="num text-right text-slate-100">{minObserved}</dd>
                  </div>
                  <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                    <dt className="text-slateish">Nivel FDR</dt>
                    <dd className="num text-right text-slate-100">{fdrAlpha.toFixed(2)}</dd>
                  </div>
                  <div className="flex items-start justify-between gap-2">
                    <dt className="text-slateish">Regiones afectadas</dt>
                    <dd className="text-right text-slate-100">
                      {data.summary.regions_affected.length ? data.summary.regions_affected.join(', ') : '—'}
                    </dd>
                  </div>
                </dl>
                <details className="group mt-3 border-t border-ink-700/60 pt-2">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-[10px] font-semibold text-slateish transition hover:text-slate-200">
                    <span>Explicación y lectura responsable</span>
                    <ChevronDown size={12} className="transition group-open:rotate-180" />
                  </summary>
                  <div className="mt-2 space-y-1.5 text-[10px] leading-relaxed text-slateish">
                    <p>{data.method}</p>
                    <p className="text-amber-100/70">{data.notes[0]}</p>
                  </div>
                </details>
              </Card>
            )}
          </div>

          <Card className="mt-4">
            <SectionHeading
              eyebrow="Listado"
              title="Anomalías"
              description={
                isBasic
                  ? 'Ordenadas por intensidad.'
                  : 'Evidencia mínima para auditar el cálculo.'
              }
              action={
                <div className="flex flex-wrap items-center gap-2">
                  <div className="relative">
                    <Search
                      size={12}
                      className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slateish"
                    />
                    <input
                      type="search"
                      value={regionQuery}
                      onChange={(event) => handleRegionQuery(event.target.value)}
                      list="anomaly-region-options"
                      placeholder="Buscar región…"
                      aria-label="Buscar anomalías por región"
                      className="focus-ring w-36 rounded-lg border border-ink-700 bg-ink-850 py-1.5 pl-7 pr-2 text-[11px] text-slate-100 outline-none transition placeholder:text-slateish hover:border-ink-600 sm:w-44"
                    />
                    <datalist id="anomaly-region-options">
                      {regionNames.map((name) => (
                        <option key={name} value={name} />
                      ))}
                    </datalist>
                  </div>
                  <div className="flex items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
                    {(['all', 'high', 'low'] as Direction[]).map((option) => (
                      <button
                        key={option}
                        type="button"
                        onClick={() => handleDirection(option)}
                        className={`focus-ring rounded-md px-2.5 py-1 text-[10px] font-semibold transition ${
                          direction === option ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                        }`}
                      >
                        {option === 'all' ? 'Todas' : option === 'high' ? 'Altas' : 'Bajas'}
                      </button>
                    ))}
                  </div>
                </div>
              }
            />
            {filtered.length === 0 ? (
              <EmptyState
                title="Sin anomalías para este filtro"
                description={
                  regionQuery
                    ? `No hay anomalías que coincidan con “${regionQuery}”. Prueba con otra región o limpia la búsqueda.`
                    : 'Cambia la dirección o relaja los parámetros del detector.'
                }
              />
            ) : (
              <>
                <div className="grid gap-2 lg:grid-cols-2">
                  {visible.map((anomaly) => (
                    <AnomalyRow
                      key={`${anomaly.date}-${anomaly.region_id}-${anomaly.sensor}`}
                      anomaly={anomaly}
                      compact={isBasic}
                    />
                  ))}
                </div>
                {filtered.length > 0 && (
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-ink-700/60 pt-3">
                    <p className="text-[10px] text-slateish">
                      Mostrando {visible.length} de {formatNumber(filtered.length)} anomalías
                    </p>
                    {visible.length < filtered.length && (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setVisibleCount((count) => Math.min(count + PAGE_SIZE, filtered.length))
                          }
                          className="focus-ring rounded-lg border border-ink-600 bg-ink-800 px-2.5 py-1.5 text-[10px] font-semibold text-slate-200 transition hover:border-ember-400/50 hover:text-ember-200"
                        >
                          Mostrar {Math.min(PAGE_SIZE, filtered.length - visible.length)} más
                        </button>
                        <button
                          type="button"
                          onClick={() => setVisibleCount(filtered.length)}
                          className="focus-ring rounded-lg border border-ink-700 px-2.5 py-1.5 text-[10px] font-semibold text-slateish transition hover:border-ink-600 hover:text-slate-200"
                        >
                          Ver todas
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </Card>

        </>
      )}
    </>
  )
}
