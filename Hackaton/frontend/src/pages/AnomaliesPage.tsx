import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  FlaskConical,
  Radar,
  ShieldAlert,
  SlidersHorizontal,
  Sparkles,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { AnomalyBars } from '../components/charts/Charts'
import { PageHeader } from '../components/layout/Layout'
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  Notice,
  SectionHeading,
  StatCard,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { SENSOR_COLORS } from '../lib/constants'
import { formatDate, formatDecimal, formatNumber } from '../lib/format'
import type { AnomaliesData, Anomaly, ApiEnvelope } from '../types/api'

const THRESHOLDS = [2.0, 2.5, 3.0, 3.5]
const WINDOWS = [0, 3, 7, 14]
const MIN_OBSERVED = [1, 3, 5, 10]
const FDR_LEVELS = [0.05, 0.1]

type Direction = 'all' | 'high' | 'low'

function AnomalyRow({ anomaly }: { anomaly: Anomaly }) {
  const high = anomaly.direction === 'high'
  return (
    <div className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
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
          <p className="num text-[10px] text-slateish">
            base {formatDecimal(anomaly.baseline_mean, 1)} ± {formatDecimal(anomaly.baseline_std, 1)}
          </p>
        </div>
      </div>

      <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <div className="rounded-lg border border-ink-700/60 bg-ink-850/60 px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-slateish">z-score</p>
          <p className={`num text-[11px] font-semibold ${high ? 'text-rose-200' : 'text-sky-200'}`}>
            {formatDecimal(anomaly.z_score, 2)}
          </p>
        </div>
        <div className="rounded-lg border border-ink-700/60 bg-ink-850/60 px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-slateish">q-valor (FDR)</p>
          <p className="num text-[11px] font-semibold text-slate-100">{anomaly.q_value.toExponential(2)}</p>
        </div>
        <div className="rounded-lg border border-ink-700/60 bg-ink-850/60 px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-slateish">Días base</p>
          <p className="num text-[11px] font-semibold text-slate-100">{formatNumber(anomaly.baseline_days)}</p>
        </div>
        <div className="rounded-lg border border-ink-700/60 bg-ink-850/60 px-2 py-1.5">
          <p className="text-[9px] uppercase tracking-wider text-slateish">Años base</p>
          <p className="num text-[11px] font-semibold text-slate-100">
            {anomaly.baseline_years.join(', ') || '—'}
          </p>
        </div>
      </div>
    </div>
  )
}

export default function AnomaliesPage() {
  const { apiPath, regionName } = useFilters()
  const [threshold, setThreshold] = useState(2.5)
  const [windowDays, setWindowDays] = useState(7)
  const [minObserved, setMinObserved] = useState(3)
  const [fdrAlpha, setFdrAlpha] = useState(0.05)
  const [direction, setDirection] = useState<Direction>('all')

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

  const filtered = useMemo(() => {
    if (!data) return []
    if (direction === 'all') return data.anomalies
    return data.anomalies.filter((item) => item.direction === direction)
  }, [data, direction])

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Radar de anomalías"
        title={`Conteos diarios inusuales · ${regionName}`}
        description="Se compara el conteo diario de detecciones con una línea base de la misma fecha ± ventana en años anteriores. Se aplica un z-score, un p-valor normal bilateral y control de falsos descubrimientos (Benjamini-Hochberg)."
        icon={Radar}
      />

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
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Días marcados"
              value={formatNumber(data.summary.flagged)}
              sub={`${formatNumber(data.summary.tests)} pruebas realizadas`}
              icon={ShieldAlert}
              accent="#FF5C16"
            />
            <StatCard
              label="Anomalías altas"
              value={formatNumber(data.summary.high_anomalies)}
              sub="Conteo por encima de la referencia"
              icon={ArrowUpRight}
              accent="#FF4D5E"
            />
            <StatCard
              label="Anomalías bajas"
              value={formatNumber(data.summary.low_anomalies)}
              sub="Conteo por debajo de la referencia"
              icon={ArrowDownRight}
              accent="#38BDF8"
            />
            <StatCard
              label="|z| máximo"
              value={data.summary.max_abs_z !== null ? formatDecimal(data.summary.max_abs_z, 2) : '—'}
              sub={`Umbral actual: ${threshold.toFixed(1)}`}
              icon={Activity}
              accent="#3DDC97"
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.3fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="Intensidad de la señal"
                title="Observado vs línea base histórica"
                description="Se muestran las anomalías con mayor |z|. La barra clara es el conteo observado; la oscura, la media histórica comparable."
              />
              {data.anomalies.length === 0 ? (
                <EmptyState
                  title="Ningún día superó todos los criterios"
                  description="Con los parámetros actuales no hay días que cumplan simultáneamente el umbral de z, el mínimo observado y el control FDR. Esto no descarta eventos."
                />
              ) : (
                <AnomalyBars anomalies={data.anomalies} />
              )}
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Método"
                title="Cómo se calcula"
                description={data.method}
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
              <div className="mt-3">
                <Notice tone="warning" title="Lectura responsable">
                  {data.notes[0]}
                </Notice>
              </div>
            </Card>
          </div>

          <Card className="mt-4">
            <SectionHeading
              eyebrow="Listado"
              title="Anomalías ordenadas por |z|"
              description="Cada fila incluye la evidencia mínima para auditar el cálculo. Descarga el CSV filtrado para reproducir el análisis."
              action={
                <div className="flex items-center gap-1 rounded-lg border border-ink-700 bg-ink-850 p-1">
                  {(['all', 'high', 'low'] as Direction[]).map((option) => (
                    <button
                      key={option}
                      type="button"
                      onClick={() => setDirection(option)}
                      className={`focus-ring rounded-md px-2.5 py-1 text-[10px] font-semibold transition ${
                        direction === option ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
                      }`}
                    >
                      {option === 'all' ? 'Todas' : option === 'high' ? 'Altas' : 'Bajas'}
                    </button>
                  ))}
                </div>
              }
            />
            {filtered.length === 0 ? (
              <EmptyState
                title="Sin anomalías para este filtro"
                description="Cambia la dirección o relaja los parámetros del detector."
              />
            ) : (
              <div className="grid gap-2 lg:grid-cols-2">
                {filtered.map((anomaly) => (
                  <AnomalyRow key={`${anomaly.date}-${anomaly.region_id}-${anomaly.sensor}`} anomaly={anomaly} />
                ))}
              </div>
            )}
          </Card>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Notice tone="neutral" title="La anomalía no es la causa" icon={FlaskConical}>
              Un conteo inusual puede deberse a más fuego, pero también a menos nubosidad, cambios en la cobertura del
              sensor o variaciones en el algoritmo. El método no atribuye causalidad.
            </Notice>
            <Notice tone="info" title="Sensibilidad y línea base" icon={Sparkles}>
              {data.notes[2] ?? 'La línea base usa el histórico disponible.'} Con {data.summary.tests} pruebas, el
              control FDR reduce falsos descubrimientos, pero no elimina el riesgo de interpretar mal un conteo.
            </Notice>
          </div>
        </>
      )}
    </div>
  )
}
