import {
  Activity,
  CalendarCheck2,
  Download,
  Flame,
  Gauge,
  LayoutDashboard,
  MapPin,
  Satellite,
} from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ConfidenceDonut, RegionBars, SensorSplit, TimeSeriesChart } from '../components/charts/Charts'
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
import { CONFIDENCE_LABELS } from '../lib/constants'
import { formatDate, formatDecimal, formatNumber, formatPercent } from '../lib/format'
import { exportUrl } from '../services/api'
import type {
  ApiEnvelope,
  DetectionsResponse,
  Summary,
  Timeseries,
} from '../types/api'

export default function DashboardPage() {
  const { meta, filters, apiPath, regionName, update } = useFilters()
  const summaryState = useApi<ApiEnvelope<Summary>>(apiPath('/stats/summary'))
  const seriesState = useApi<ApiEnvelope<Timeseries>>(
    apiPath('/stats/timeseries', { granularity: 'month' }),
  )
  const recentState = useApi<DetectionsResponse>(
    apiPath('/detections', { limit: 8, order: 'desc' }),
  )

  const summary = summaryState.data?.data
  const series = seriesState.data?.data
  const recent = recentState.data?.data ?? []

  const topRegion = summary?.by_region[0]
  const topProvince = summary?.by_province[0]
  const sensorsLabel = useMemo(() => {
    if (!summary) return '—'
    return summary.by_sensor.map((item) => item.sensor).join(' + ') || '—'
  }, [summary])

  if (summaryState.error) {
    return <ErrorState message={summaryState.error} onRetry={summaryState.refetch} />
  }

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Panel general"
        title={`Resumen de focos de calor · ${regionName}`}
        description="Indicadores calculados directamente sobre las detecciones NASA FIRMS disponibles. Los conteos describen detecciones de píxeles, no incendios confirmados ni superficie quemada."
        icon={LayoutDashboard}
        actions={
          <a
            href={exportUrl(apiPath('/export/detections.csv'))}
            className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60 hover:bg-ember-500/15"
          >
            <Download size={14} /> Exportar CSV filtrado
          </a>
        }
      />

      {summaryState.loading && !summary ? (
        <LoadingBlock label="Calculando indicadores del periodo…" />
      ) : !summary || summary.total === 0 ? (
        <Card>
          <EmptyState
            title="No hay detecciones para los filtros seleccionados"
            description="Ajusta el periodo, la región, el sensor o el filtro de calidad. La aplicación no rellena vacíos con datos inventados."
          />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Detecciones"
              value={formatNumber(summary.total)}
              sub={`${formatDecimal(summary.detections_per_day, 2)} detecciones/día en el periodo`}
              icon={Flame}
            />
            <StatCard
              label="Días con actividad"
              value={formatNumber(summary.active_days)}
              sub={`de ${formatNumber(summary.days_in_period)} días analizados`}
              icon={CalendarCheck2}
              accent="#3DDC97"
            />
            <StatCard
              label="Sensores"
              value={sensorsLabel}
              sub={summary.by_sensor
                .map((item) => `${item.sensor}: ${formatNumber(item.count)}`)
                .join(' · ')}
              icon={Satellite}
              accent="#FFB020"
            />
            <StatCard
              label="FRP acumulado"
              value={summary.frp.sum !== null ? `${formatDecimal(summary.frp.sum, 0)} MW` : '—'}
              sub={
                summary.frp.mean !== null
                  ? `Media ${formatDecimal(summary.frp.mean)} MW · máx ${formatDecimal(summary.frp.max)} MW`
                  : 'Sin valores de FRP válidos'
              }
              icon={Gauge}
              accent="#FF4D5E"
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="Evolución temporal"
                title="Detecciones por mes y sensor"
                description="Serie mensual calculada con la fecha local de adquisición. Los valores faltantes indican ausencia de detecciones o de cobertura, no necesariamente ausencia de fuego."
              />
              {seriesState.loading && !series ? (
                <LoadingBlock compact />
              ) : (
                <TimeSeriesChart series={series?.series ?? []} granularity="month" height={300} />
              )}
              <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px] text-slateish">
                <Badge tone="info">MODIS ~1 km</Badge>
                <Badge tone="critical">VIIRS ~375 m</Badge>
                <span>
                  Periodo: {formatDate(summary.period.start)} — {formatDate(summary.period.end)}
                </span>
              </div>
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Calidad"
                title="Distribución de confianza"
                description="MODIS se clasifica con sus umbrales 0–100 (baja &lt;30, nominal 30–79, alta ≥80). VIIRS usa sus categorías low/nominal/high. Los esquemas no son equivalentes."
              />
              <ConfidenceDonut values={summary.by_confidence} />
              <div className="mt-3 rounded-xl border border-ink-700/70 bg-ink-800/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slateish">
                  Reparto por sensor
                </p>
                <div className="mt-2">
                  <SensorSplit sensors={summary.by_sensor} />
                </div>
              </div>
            </Card>
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_1fr_1.1fr]">
            <Card>
              <SectionHeading
                eyebrow="Distribución espacial"
                title="Regiones naturales"
                description="Haz clic en una región para filtrar todo el tablero."
              />
              <RegionBars
                regions={summary.by_region}
                onSelect={(regionId) => update({ region: regionId })}
              />
              {topRegion && (
                <p className="mt-3 text-[11px] leading-relaxed text-slateish">
                  Mayor concentración: <span className="text-slate-200">{topRegion.region}</span> con{' '}
                  <span className="num text-slate-200">{formatNumber(topRegion.count)}</span> detecciones (
                  {formatPercent(topRegion.share)} del total).
                </p>
              )}
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Territorio"
                title="Provincias con más detecciones"
                description="Top 10 del periodo. La provincia se asigna con geometrías Natural Earth 1:10m."
              />
              <div className="space-y-1.5">
                {summary.by_province.map((province, index) => (
                  <button
                    key={province.province_id}
                    type="button"
                    onClick={() => update({ region: province.province_id })}
                    className="focus-ring flex w-full items-center gap-2 rounded-lg border border-transparent px-2 py-1.5 text-left text-[11px] transition hover:border-ink-700 hover:bg-ink-800/60"
                  >
                    <span className="num w-4 text-[10px] text-slateish">{String(index + 1).padStart(2, '0')}</span>
                    <span className="min-w-0 flex-1 truncate text-slate-200">{province.province}</span>
                    <span className="num text-slate-100">{formatNumber(province.count)}</span>
                    <span className="num w-10 text-right text-[10px] text-slateish">
                      {formatPercent(province.share)}
                    </span>
                  </button>
                ))}
              </div>
              {topProvince && (
                <p className="mt-3 flex items-center gap-1 text-[10px] text-slateish">
                  <MapPin size={11} /> {topProvince.province} · {topProvince.region_id}
                </p>
              )}
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Trazabilidad"
                title="Últimas detecciones"
                description="Registros más recientes del periodo filtrado, ordenados por fecha UTC de adquisición."
                action={
                  <Link
                    to="/mapa"
                    className="focus-ring inline-flex items-center gap-1 rounded-md border border-ink-700 px-2 py-1 text-[10px] font-semibold text-slateish transition hover:border-ember-400/40 hover:text-ember-200"
                  >
                    Ver mapa
                  </Link>
                }
              />
              {recentState.loading && !recent.length ? (
                <LoadingBlock compact />
              ) : (
                <div className="space-y-1.5">
                  {recent.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center gap-2 rounded-lg border border-ink-700/60 bg-ink-800/40 px-2 py-1.5 text-[10px]"
                    >
                      <span
                        className="h-1.5 w-1.5 shrink-0 rounded-full"
                        style={{ background: item.sensor === 'MODIS' ? '#FFB020' : '#FF4D5E' }}
                      />
                      <span className="num text-slate-200">{item.acq_date_local}</span>
                      <span className="num text-slateish">{item.acq_time_local}</span>
                      <span className="min-w-0 flex-1 truncate text-slate-300">{item.province}</span>
                      <span className="rounded border border-ink-600 px-1 text-[9px] uppercase text-slateish">
                        {CONFIDENCE_LABELS[item.confidence_level] ?? item.confidence_level}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-3 flex items-start gap-1.5 text-[10px] leading-relaxed text-slateish">
                <Activity size={11} className="mt-0.5 shrink-0" />
                <span>
                  Dataset {meta.dataset_version ?? 'sin versión'} · {formatNumber(meta.by_sensor.MODIS ?? 0)}{' '}
                  MODIS / {formatNumber(meta.by_sensor.VIIRS ?? 0)} VIIRS en total.
                </span>
              </div>
            </Card>
          </div>

          {summary.notes.length > 0 && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Notice tone="warning" title="Advertencia de interpretación">
                {summary.notes[0]}
              </Notice>
              <Notice tone="neutral" title="Cobertura del dataset">
                Periodo filtrado: {filters.start} → {filters.end}. Cobertura total disponible:{' '}
                {formatDate(meta.date_range.start)} a {formatDate(meta.date_range.end)}. Los vacíos de VIIRS o MODIS
                en algunos tramos reflejan la disponibilidad real de los productos.
              </Notice>
            </div>
          )}
        </>
      )}
    </div>
  )
}
