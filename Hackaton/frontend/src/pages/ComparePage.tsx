import {
  Download,
  Gauge,
  GitCompareArrows,
  Layers3,
  Satellite,
  Waves,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { TimeSeriesChart } from '../components/charts/Charts'
import { PageHeader } from '../components/layout/Layout'
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  SectionHeading,
  StatCard,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { CONFIDENCE_LABELS, SENSOR_COLORS } from '../lib/constants'
import { formatDecimal, formatNumber, formatPercent } from '../lib/format'
import { exportUrl } from '../services/api'
import type { ApiEnvelope, Comparison, Granularity, SensorComparison } from '../types/api'

const GRANULARITIES: { id: Granularity; label: string }[] = [
  { id: 'month', label: 'Mensual' },
  { id: 'week', label: 'Semanal' },
  { id: 'day', label: 'Diario' },
]

function SensorCard({ data, compact = false }: { data: SensorComparison; compact?: boolean }) {
  const color = SENSOR_COLORS[data.sensor]
  return (
    <div className="panel relative overflow-hidden p-4">
      <div
        className="pointer-events-none absolute -right-10 -top-10 h-28 w-28 rounded-full opacity-20 blur-2xl"
        style={{ background: color }}
      />
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
          <h3 className="text-sm font-semibold text-white">{data.sensor}</h3>
        </div>
        <Badge tone={data.sensor === 'MODIS' ? 'warning' : 'critical'}>
          {data.sensor === 'MODIS' ? '~1 km' : '~375 m'}
        </Badge>
      </div>
      <p className="num mt-3 text-2xl font-semibold text-white">{formatNumber(data.count)}</p>
      <p className="text-[10px] text-slateish">{formatPercent(data.share)} de las detecciones del periodo</p>

      {compact ? (
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
            <p className="text-[9px] uppercase tracking-wider text-slateish">Cobertura</p>
            <p className="num mt-0.5 text-slate-100">{formatPercent(data.coverage)}</p>
          </div>
          <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
            <p className="text-[9px] uppercase tracking-wider text-slateish">Días activos</p>
            <p className="num mt-0.5 text-slate-100">{formatNumber(data.active_days)}</p>
          </div>
        </div>
      ) : (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
            <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
              <p className="text-[9px] uppercase tracking-wider text-slateish">Cobertura</p>
              <p className="num mt-0.5 text-slate-100">{formatPercent(data.coverage)}</p>
            </div>
            <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
              <p className="text-[9px] uppercase tracking-wider text-slateish">Días activos</p>
              <p className="num mt-0.5 text-slate-100">{formatNumber(data.active_days)}</p>
            </div>
            <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
              <p className="text-[9px] uppercase tracking-wider text-slateish">Media diaria</p>
              <p className="num mt-0.5 text-slate-100">{formatDecimal(data.mean_daily, 2)}</p>
            </div>
            <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
              <p className="text-[9px] uppercase tracking-wider text-slateish">Máximo diario</p>
              <p className="num mt-0.5 text-slate-100">{formatNumber(data.max_daily)}</p>
            </div>
          </div>

          <div className="mt-3 space-y-1.5">
            <p className="text-[9px] font-semibold uppercase tracking-wider text-slateish">Confianza</p>
            <div className="flex h-2.5 overflow-hidden rounded-full bg-ink-800">
              {Object.entries(data.confidence).map(([level, value]) => (
                <div
                  key={level}
                  style={{
                    width: `${(value / Math.max(1, data.count)) * 100}%`,
                    background:
                      level === 'high' ? '#3DDC97' : level === 'nominal' ? '#FFB020' : '#64748B',
                  }}
                  title={`${CONFIDENCE_LABELS[level] ?? level}: ${formatNumber(value)}`}
                />
              ))}
            </div>
            <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[9px] text-slateish">
              {Object.entries(data.confidence).map(([level, value]) => (
                <span key={level}>
                  {CONFIDENCE_LABELS[level] ?? level}: {formatNumber(value)}
                </span>
              ))}
            </div>
          </div>

          <div className="mt-3 border-t border-ink-700/60 pt-2">
            <p className="text-[9px] font-semibold uppercase tracking-wider text-slateish">Plataformas</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {data.satellites.map((item) => (
                <span
                  key={item.satellite}
                  className="rounded border border-ink-700 bg-ink-800/60 px-1.5 py-0.5 text-[9px] text-slate-200"
                >
                  {item.satellite} · {formatNumber(item.count)}
                </span>
              ))}
            </div>
            <p className="mt-1.5 text-[9px] leading-relaxed text-slateish">
              Productos: {data.products.map((item) => `${item.product} (${formatNumber(item.count)})`).join(', ')}
            </p>
          </div>
        </>
      )}
    </div>
  )
}

export default function ComparePage() {
  const { meta, apiPath, regionName, viewMode, setViewMode } = useFilters()
  const [granularity, setGranularity] = useState<Granularity>('month')
  const isBasic = viewMode === 'basic'
  const comparisonState = useApi<ApiEnvelope<Comparison>>(
    apiPath('/comparison', { granularity }),
  )
  const comparison = comparisonState.data?.data

  const regionRows = useMemo(() => {
    if (!comparison) return []
    const map = new Map<string, { region: string; MODIS: number; VIIRS: number }>()
    comparison.by_region.forEach((row) => {
      const entry = map.get(row.region_id) ?? { region: row.region, MODIS: 0, VIIRS: 0 }
      entry[row.sensor] += row.count
      map.set(row.region_id, entry)
    })
    return Array.from(map.values()).sort(
      (a, b) => b.MODIS + b.VIIRS - (a.MODIS + a.VIIRS),
    )
  }, [comparison])

  const regionMax = regionRows.reduce(
    (max, row) => Math.max(max, row.MODIS + row.VIIRS),
    0,
  )

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Comparador de sensores"
        title={`MODIS vs VIIRS · ${regionName}`}
        icon={GitCompareArrows}
        actions={
          isBasic ? (
            <button
              type="button"
              onClick={() => setViewMode('expert')}
              className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20"
            >
              <Gauge size={14} /> Cambiar a Modo Experto
            </button>
          ) : (
            <a
              href={exportUrl(apiPath('/export/detections.csv'))}
              className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
            >
              <Download size={14} /> Descargar datos
            </a>
          )
        }
      />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 rounded-lg border border-ink-700 bg-ink-850 p-1">
          {GRANULARITIES.map((option) => (
            <button
              key={option.id}
              type="button"
              onClick={() => setGranularity(option.id)}
              className={`focus-ring rounded-md px-3 py-1.5 text-[11px] font-semibold transition ${
                granularity === option.id ? 'bg-ink-700 text-white' : 'text-slateish hover:text-slate-200'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <p className="text-[10px] text-slateish">
          Mismo periodo y filtros para ambos sensores · {meta.date_by_sensor.MODIS?.count ?? 0} MODIS /{' '}
          {meta.date_by_sensor.VIIRS?.count ?? 0} VIIRS en el dataset completo
        </p>
      </div>

      {comparisonState.error ? (
        <ErrorState message={comparisonState.error} onRetry={comparisonState.refetch} />
      ) : comparisonState.loading && !comparison ? (
        <LoadingBlock label="Comparando sensores…" />
      ) : !comparison || comparison.total === 0 ? (
        <Card>
          <EmptyState
            title="No hay detecciones para comparar"
            description="Prueba un periodo más amplio o quita el filtro de sensor. Si un sensor no tiene datos en el periodo, no se inventan valores."
          />
        </Card>
      ) : (
        <>
          <div className={`grid grid-cols-2 gap-3 ${isBasic ? 'lg:grid-cols-2' : 'lg:grid-cols-3'}`}>
            <StatCard
              label="Total comparado"
              value={formatNumber(comparison.total)}
              sub={`${comparison.period.days} días · ${regionName}`}
              icon={Layers3}
            />
            {!isBasic && (
              <StatCard
                label="Sensores presentes"
                value={String(comparison.by_sensor.length)}
                sub={comparison.by_sensor.map((item) => item.sensor).join(' + ')}
                icon={Satellite}
                accent="#FFB020"
              />
            )}
            <StatCard
              label="Cobertura del periodo"
              value={`${comparison.period.days} d`}
              sub="Días calendario analizados"
              icon={Waves}
              accent="#3DDC97"
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {comparison.by_sensor.map((item) => (
              <SensorCard key={item.sensor} data={item} compact={isBasic} />
            ))}
          </div>

          <div className={`mt-4 ${isBasic ? '' : 'grid gap-4 xl:grid-cols-[1.5fr_1fr]'}`}>
            <Card>
              <SectionHeading
                eyebrow="Serie comparada"
                title={`Detecciones por ${granularity === 'month' ? 'mes' : granularity === 'week' ? 'semana' : 'día'}`}
                description={
                  isBasic
                    ? 'Misma escala y filtros para ambos sensores.'
                    : 'Ambas series usan exactamente el mismo periodo y filtros. Si un sensor no tiene datos en un tramo, la línea puede quedar vacía.'
                }
              />
              <TimeSeriesChart
                series={comparison.series}
                granularity={granularity}
                height={320}
              />
            </Card>

            {!isBasic && (
              <Card>
                <SectionHeading
                  eyebrow="Distribución regional"
                  title="Conteos por región natural"
                  description="Barras agrupadas por sensor. Permite ver si la diferencia entre sensores es uniforme o depende del territorio."
                />
                {regionRows.length === 0 ? (
                  <EmptyState title="Sin desglose regional" />
                ) : (
                  <div className="space-y-3">
                    {regionRows.map((row) => {
                      const total = row.MODIS + row.VIIRS
                      return (
                        <div key={row.region}>
                          <div className="mb-1 flex items-center justify-between text-[11px]">
                            <span className="text-slate-200">{row.region}</span>
                            <span className="num text-slateish">{formatNumber(total)}</span>
                          </div>
                          <div className="flex h-2.5 overflow-hidden rounded-full bg-ink-800">
                            <div
                              style={{
                                width: `${regionMax ? (row.MODIS / regionMax) * 100 : 0}%`,
                                background: SENSOR_COLORS.MODIS,
                              }}
                              title={`MODIS: ${formatNumber(row.MODIS)}`}
                            />
                            <div
                              style={{
                                width: `${regionMax ? (row.VIIRS / regionMax) * 100 : 0}%`,
                                background: SENSOR_COLORS.VIIRS,
                              }}
                              title={`VIIRS: ${formatNumber(row.VIIRS)}`}
                            />
                          </div>
                          <div className="mt-1 flex gap-3 text-[9px] text-slateish">
                            <span>MODIS {formatNumber(row.MODIS)}</span>
                            <span>VIIRS {formatNumber(row.VIIRS)}</span>
                          </div>
                        </div>
                      )
                    })}
                  </div>
                )}
              </Card>
            )}
          </div>
        </>
      )}
    </div>
  )
}
