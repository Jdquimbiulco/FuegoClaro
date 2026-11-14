import {
  Activity,
  ArrowRight,
  CalendarCheck2,
  CheckCircle2,
  Download,
  Flame,
  Gauge,
  Info,
  Layers,
  LayoutDashboard,
  MapPin,
  Radio,
  Satellite,
  ShieldAlert,
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
  const { meta, filters, apiPath, regionName, update, viewMode, setViewMode } = useFilters()
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

  const modisData = useMemo(() => summary?.by_sensor.find((s) => s.sensor === 'MODIS'), [summary])
  const viirsData = useMemo(() => summary?.by_sensor.find((s) => s.sensor === 'VIIRS'), [summary])
  const modisCount = modisData?.count ?? 0
  const viirsCount = viirsData?.count ?? 0
  const modisShare = modisData?.share ?? 0
  const viirsShare = viirsData?.share ?? 0

  const highConfidenceCount = summary?.by_confidence?.high ?? 0
  const highConfidenceShare = summary?.total ? highConfidenceCount / summary.total : 0

  if (summaryState.error) {
    return <ErrorState message={summaryState.error} onRetry={summaryState.refetch} />
  }

  const isBasic = viewMode === 'basic'

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow={isBasic ? 'Visión General' : 'Telemetría Satelital Avanzada'}
        title={
          isBasic
            ? `Monitoreo de actividad térmica · ${regionName}`
            : `Panel Analítico de Sensores & FRP · ${regionName}`
        }
        description={
          isBasic
            ? 'Vista clara y accesible para el público general y tomadores de decisiones. Muestra la intensidad térmica reciente en el territorio.'
            : 'Telemetría orbital calibrada de NASA FIRMS (MODIS Collection 6.1 y VIIRS 375 m). Análisis detallado de potencia radiativa, confianza algorítmica y distribución espacial.'
        }
        icon={LayoutDashboard}
        actions={
          <div className="flex items-center gap-2">
            {isBasic ? (
              <button
                type="button"
                onClick={() => setViewMode('expert')}
                className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-sky-400/40 bg-sky-500/15 px-3 py-2 text-xs font-bold text-sky-200 transition hover:bg-sky-500/25 shadow-sm"
              >
                <Gauge size={14} /> Cambiar a Modo Experto
              </button>
            ) : (
              <a
                href={exportUrl(apiPath('/export/detections.csv'))}
                className="focus-ring inline-flex items-center gap-2 rounded-lg border border-sky-400/40 bg-sky-500/15 px-3 py-2 text-xs font-semibold text-sky-100 transition hover:border-sky-300/70 hover:bg-sky-500/25"
              >
                <Download size={14} /> Exportar Dataset CSV
              </a>
            )}
          </div>
        }
      />

      {/* Banner de Acceso al Módulo Especializado de Incendios */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ember-400/30 bg-gradient-to-r from-ember-500/15 via-ember-500/10 to-transparent p-3.5 sm:p-4">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-ember-400/30 bg-ember-500/20 text-ember-300 shadow-ember">
            <ShieldAlert size={20} />
          </span>
          <div>
            <p className="text-sm font-semibold text-white">¿Buscas incendios forestales confirmados y alertas críticas?</p>
            <p className="text-xs text-slateish">
              Visita el nuevo módulo con eventos agrupados (DBSCAN), descarte de falsos positivos y mapa de susceptibilidad.
            </p>
          </div>
        </div>
        <Link
          to="/incendios"
          className="focus-ring inline-flex items-center gap-1.5 rounded-lg bg-ember-500 px-3.5 py-2 text-xs font-bold text-slate-950 transition hover:bg-ember-400"
        >
          Ver Módulo de Incendios <ArrowRight size={13} />
        </Link>
      </div>

      {summaryState.loading && !summary ? (
        <LoadingBlock label="Calculando indicadores del periodo…" />
      ) : !summary || summary.total === 0 ? (
        <Card>
          <EmptyState
            title="No hay detecciones para los filtros seleccionados"
            description="Ajusta el periodo, la región, el sensor o el filtro de calidad. La aplicación no rellena vacíos con datos inventados."
          />
        </Card>
      ) : isBasic ? (
        /* VISTA BÁSICA / PÚBLICO GENERAL */
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Focos térmicos detectados"
              value={formatNumber(summary.total)}
              sub={`${formatDecimal(summary.detections_per_day, 1)} detecciones promedio/día`}
              icon={Flame}
            />
            <StatCard
              label="Días con actividad"
              value={formatNumber(summary.active_days)}
              sub={`de ${formatNumber(summary.days_in_period)} días evaluados`}
              icon={CalendarCheck2}
              accent="#3DDC97"
            />
            <StatCard
              label="Nivel de actividad"
              value={
                summary.detections_per_day > 25
                  ? 'Actividad Alta'
                  : summary.detections_per_day > 8
                    ? 'Actividad Moderada'
                    : 'Actividad Baja'
              }
              sub="Evaluado por frecuencia diaria"
              icon={Activity}
              accent={
                summary.detections_per_day > 25
                  ? '#FF4D5E'
                  : summary.detections_per_day > 8
                    ? '#FFB020'
                    : '#3DDC97'
              }
            />
            <StatCard
              label="Mayor concentración"
              value={topProvince?.province ?? topRegion?.region ?? regionName}
              sub={
                topProvince
                  ? `${formatPercent(topProvince.share)} de los focos en el periodo`
                  : 'Sin concentración provincial'
              }
              icon={MapPin}
              accent="#FFB020"
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="Tendencia"
                title="Evolución de actividad por mes"
                description="Número de puntos calientes detectados por mes en la zona analizada."
              />
              {seriesState.loading && !series ? (
                <LoadingBlock compact />
              ) : (
                <TimeSeriesChart series={series?.series ?? []} granularity="month" height={280} />
              )}
              <p className="mt-3 text-[11px] text-slateish">
                Los picos históricos en Ecuador suelen concentrarse entre agosto y noviembre debido a la estación seca y vientos fuertes.
              </p>
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Geografía"
                title="Zonas con mayor registro"
                description="Top de provincias con más detecciones térmicas."
              />
              <div className="space-y-2 mt-2">
                {summary.by_province.slice(0, 5).map((province, index) => (
                  <button
                    key={province.province_id}
                    type="button"
                    onClick={() => update({ region: province.province_id })}
                    className="focus-ring flex w-full flex-col gap-1 rounded-lg border border-ink-700/60 bg-ink-800/40 p-2.5 text-left transition hover:border-ember-400/40 hover:bg-ink-800/80"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-200">
                        {index + 1}. {province.province}
                      </span>
                      <span className="num font-bold text-white">{formatNumber(province.count)}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] text-slateish">
                      <span>Proporción del total</span>
                      <span className="num font-medium text-ember-300">{formatPercent(province.share)}</span>
                    </div>
                    <div className="h-1.5 w-full rounded-full bg-ink-700 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-gradient-to-r from-ember-500 to-amber-400"
                        style={{ width: `${Math.min(100, Math.max(8, province.share * 100))}%` }}
                      />
                    </div>
                  </button>
                ))}
              </div>
            </Card>
          </div>

          <div className="mt-4 rounded-xl border border-ink-700/70 bg-ink-850/80 p-4">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 rounded-lg border border-amber-400/30 bg-amber-500/10 p-2 text-amber-300">
                <Info size={18} />
              </span>
              <div className="space-y-1 text-xs leading-relaxed text-slateish">
                <p className="font-semibold text-slate-200">
                  ¿Cómo interpretar estos datos satelitales?
                </p>
                <p>
                  Un foco de calor es una anomalía térmica de superficie registrada por los satélites de la NASA.
                  <strong> No todo foco equivale a un incendio forestal</strong>: puede deberse a quemas agrícolas programadas o fuentes industriales de calor.
                </p>
                <p className="text-[11px] text-slate-400">
                  Si eres investigador, bombero o analista y necesitas la calibración matemática de FRP (MW), comparación sensor a sensor y telemetría exacta, usa el botón <strong>&quot;Modo Experto&quot;</strong> en la esquina superior.
                </p>
              </div>
            </div>
          </div>
        </>
      ) : (
        /* VISTA AVANZADA / EXPERTOS */
        <>
          {/* Banner de Contexto Científico para el Modo Experto */}
          <div className="mb-4 rounded-xl border border-sky-400/30 bg-gradient-to-r from-sky-500/15 via-ink-850 to-ink-900 p-4 shadow-panel">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-start gap-3">
                <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-sky-400/40 bg-sky-500/20 text-sky-300 shadow-sm">
                  <Radio size={18} />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-bold uppercase tracking-wider text-sky-300">
                      Panel Analítico Científico Activo
                    </span>
                    <Badge tone="info">MODIS ~1 km vs VIIRS ~375 m</Badge>
                    <Badge tone="neutral">Sistema WGS84 · UTC-5</Badge>
                  </div>
                  <p className="mt-1 text-xs text-slate-300 leading-relaxed">
                    Telemetría térmica armonizada. Recuerda: <strong>VIIRS registra hasta 4 veces más detecciones</strong> que MODIS para un mismo evento debido a su mayor resolución espacial (375 m vs 1 km). No deben sumarse como hectáreas de superficie quemada.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2 text-xs text-slateish">
                <span className="flex items-center gap-1.5">
                  <CheckCircle2 size={13} className="text-mint" /> Calibración NASA FIRMS
                </span>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Detecciones de Píxel"
              value={formatNumber(summary.total)}
              sub={`${formatDecimal(summary.detections_per_day, 2)} obs/día · ${summary.active_days} días activos`}
              icon={Flame}
            />
            <StatCard
              label="Balance VIIRS / MODIS"
              value={`${formatNumber(viirsCount)} / ${formatNumber(modisCount)}`}
              sub={`VIIRS: ${formatPercent(viirsShare)} · MODIS: ${formatPercent(modisShare)}`}
              icon={Satellite}
              accent="#FFB020"
            />
            <StatCard
              label="Energía Radiativa (FRP)"
              value={summary.frp.sum !== null ? `${formatDecimal(summary.frp.sum, 0)} MW` : '—'}
              sub={
                summary.frp.mean !== null
                  ? `Media: ${formatDecimal(summary.frp.mean, 1)} MW · Pico: ${formatDecimal(summary.frp.max, 1)} MW`
                  : 'Sin valores de FRP válidos'
              }
              icon={Gauge}
              accent="#FF4D5E"
            />
            <StatCard
              label="Alta Confiabilidad"
              value={`${formatPercent(highConfidenceShare)}`}
              sub={`${formatNumber(highConfidenceCount)} registros con certeza máxima`}
              icon={Activity}
              accent="#3DDC97"
            />
          </div>

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="Evolución Temporal & Comparativa"
                title="Detecciones por mes desagregadas por sensor"
                description="Serie mensual por fecha local. La discrepancia entre sensores refleja la mayor resolución de VIIRS, no un aumento real en la superficie física del fuego."
              />
              {seriesState.loading && !series ? (
                <LoadingBlock compact />
              ) : (
                <TimeSeriesChart series={series?.series ?? []} granularity="month" height={300} />
              )}
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-ink-700/60 pt-3 text-[11px] text-slateish">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone="info">MODIS Terra/Aqua (1 km)</Badge>
                  <Badge tone="critical">VIIRS NOAA-20 (375 m)</Badge>
                </div>
                <span>
                  Ventana analizada: {formatDate(summary.period.start)} — {formatDate(summary.period.end)}
                </span>
              </div>
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Calidad & Calibración"
                title="Distribución de confianza estadística"
                description="Taxonomía bimodal: MODIS clasifica en umbrales continuos 0-100 (baja <30, nominal 30-79, alta ≥80) y VIIRS en categorías discretas (low, nominal, high)."
              />
              <ConfidenceDonut values={summary.by_confidence} />
              <div className="mt-3 rounded-xl border border-ink-700/70 bg-ink-800/50 p-3">
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slateish">
                  Reparto porcentual de observaciones
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
                eyebrow="Distribución Espacial"
                title="Regiones naturales de Ecuador"
                description="Proporción territorial. Haz clic en una región para filtrar todo el dashboard."
              />
              <RegionBars
                regions={summary.by_region}
                onSelect={(regionId) => update({ region: regionId })}
              />
              {topRegion && (
                <p className="mt-3 text-[11px] leading-relaxed text-slateish border-t border-ink-700/60 pt-2.5">
                  Región más afectada: <strong className="text-white">{topRegion.region}</strong> con{' '}
                  <span className="num font-semibold text-ember-300">{formatNumber(topRegion.count)}</span> detecciones (
                  {formatPercent(topRegion.share)} del total nacional).
                </p>
              )}
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Territorio"
                title="Top 10 provincias con más focos"
                description="Asignación espacial mediante geometrías vectoriales Natural Earth 1:10m."
              />
              <div className="space-y-1.5 mt-2">
                {summary.by_province.map((province, index) => (
                  <button
                    key={province.province_id}
                    type="button"
                    onClick={() => update({ region: province.province_id })}
                    className="focus-ring flex w-full items-center gap-2 rounded-lg border border-transparent px-2 py-1.5 text-left text-[11px] transition hover:border-ink-700 hover:bg-ink-800/60"
                  >
                    <span className="num w-4 text-[10px] font-bold text-slateish">{String(index + 1).padStart(2, '0')}</span>
                    <span className="min-w-0 flex-1 truncate font-medium text-slate-200">{province.province}</span>
                    <span className="num font-semibold text-slate-100">{formatNumber(province.count)}</span>
                    <span className="num w-11 text-right text-[10px] text-ember-300 font-medium">
                      {formatPercent(province.share)}
                    </span>
                  </button>
                ))}
              </div>
              {topProvince && (
                <p className="mt-3 flex items-center gap-1 text-[10px] text-slateish border-t border-ink-700/60 pt-2">
                  <MapPin size={11} className="text-ember-400" /> Provincia líder: {topProvince.province} ({topProvince.region_id})
                </p>
              )}
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Telemetría Reciente"
                title="Registro de últimas observaciones"
                description="Últimos píxeles térmicos adquiridos en tiempo casi real."
                action={
                  <Link
                    to="/mapa"
                    className="focus-ring inline-flex items-center gap-1 rounded-md border border-ink-700 px-2 py-1 text-[10px] font-semibold text-slateish transition hover:border-sky-400/40 hover:text-sky-200"
                  >
                    Ver en mapa
                  </Link>
                }
              />
              {recentState.loading && !recent.length ? (
                <LoadingBlock compact />
              ) : (
                <div className="space-y-1.5 mt-2">
                  {recent.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center gap-2 rounded-lg border border-ink-700/60 bg-ink-800/40 px-2.5 py-1.5 text-[10px]"
                    >
                      <span
                        className="h-2 w-2 shrink-0 rounded-full"
                        style={{ background: item.sensor === 'MODIS' ? '#FFB020' : '#FF4D5E' }}
                        title={`Sensor: ${item.sensor}`}
                      />
                      <span className="num font-semibold text-slate-200">{item.acq_date_local}</span>
                      <span className="num text-slateish">{item.acq_time_local}</span>
                      <span className="min-w-0 flex-1 truncate text-slate-300">{item.province}</span>
                      <span className="rounded border border-ink-600 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-slateish">
                        {CONFIDENCE_LABELS[item.confidence_level] ?? item.confidence_level}
                      </span>
                    </div>
                  ))}
                </div>
              )}
              <div className="mt-3 flex items-start gap-1.5 text-[10px] leading-relaxed text-slateish border-t border-ink-700/60 pt-2">
                <Layers size={11} className="mt-0.5 shrink-0 text-sky-400" />
                <span>
                  Dataset {meta.dataset_version ?? 'sin versión'} · {formatNumber(meta.by_sensor.MODIS ?? 0)} MODIS / {formatNumber(meta.by_sensor.VIIRS ?? 0)} VIIRS totales en base de datos.
                </span>
              </div>
            </Card>
          </div>

          {summary.notes.length > 0 && (
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <Notice tone="warning" title="Advertencia Metodológica de Sensores">
                {summary.notes[0]}
              </Notice>
              <Notice tone="neutral" title="Cobertura y Calibración Espaciotemporal">
                Periodo filtrado: {filters.start} → {filters.end}. Cobertura disponible:{' '}
                {formatDate(meta.date_range.start)} a {formatDate(meta.date_range.end)}. Los vacíos de detección entre satélites reflejan las horas de sobrevuelo orbital y nubosidad, no necesariamente ausencia de fuego.
              </Notice>
            </div>
          )}
        </>
      )}
    </div>
  )
}
