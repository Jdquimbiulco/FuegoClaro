import {
  Activity,
  AlertTriangle,
  CalendarCheck2,
  CheckCircle2,
  Compass,
  Download,
  Flame,
  Gauge,
  Layers,
  LayoutDashboard,
  MapPin,
  PhoneCall,
  Radio,
  Satellite,
  ShieldAlert,
  TreePine,
  Wind,
} from 'lucide-react'
import { useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ConfidenceDonut, RegionBars, SensorSplit, TimeSeriesChart } from '../components/charts/Charts'
import { PageHeader } from '../components/layout/Layout'
import { FiltersBar } from '../components/layout/FiltersBar'
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

  const sensorCardData = useMemo(() => {
    if (filters.sensor === 'MODIS') {
      return {
        label: 'Sensor Activo: MODIS',
        value: formatNumber(modisCount),
        sub: '100% de la selección · ~1 km (Terra/Aqua)',
      }
    }
    if (filters.sensor === 'VIIRS') {
      return {
        label: 'Sensor Activo: VIIRS',
        value: formatNumber(viirsCount),
        sub: '100% de la selección · ~375 m (NOAA-20)',
      }
    }
    if (viirsCount === 0 && modisCount > 0) {
      return {
        label: 'Sensor: Solo MODIS',
        value: formatNumber(modisCount),
        sub: 'Solo se registraron focos con MODIS en este periodo',
      }
    }
    if (modisCount === 0 && viirsCount > 0) {
      return {
        label: 'Sensor: Solo VIIRS',
        value: formatNumber(viirsCount),
        sub: 'Solo se registraron focos con VIIRS en este periodo',
      }
    }
    if (viirsCount === 0 && modisCount === 0) {
      return {
        label: 'Balance VIIRS / MODIS',
        value: '0',
        sub: 'Sin registros para los filtros seleccionados',
      }
    }
    return {
      label: 'Balance VIIRS / MODIS',
      value: `${formatNumber(viirsCount)} / ${formatNumber(modisCount)}`,
      sub: `VIIRS: ${formatPercent(viirsShare)} · MODIS: ${formatPercent(modisShare)}`,
    }
  }, [filters.sensor, modisCount, modisShare, viirsCount, viirsShare])

  const alertLevel = useMemo(() => {
    if (!summary || summary.total === 0) {
      return {
        label: 'Sin actividad relevante',
        tone: 'positive' as const,
        badge: 'Nivel Normal / Seguro',
        desc: 'No se registran anomalías térmicas significativas en el periodo y territorio seleccionados.',
        bg: 'from-emerald-950/40 via-ink-850 to-ink-900',
        border: 'border-emerald-500/40',
        textColor: 'text-emerald-400',
        icon: CheckCircle2,
      }
    }
    if (summary.detections_per_day > 25) {
      return {
        label: 'Alerta Alta en el Territorio',
        tone: 'critical' as const,
        badge: 'Alerta Roja / Riesgo Alto',
        desc: 'Alta frecuencia de calor detectada. Las condiciones de sequía y vientos favorecen la rápida propagación del fuego.',
        bg: 'from-red-950/40 via-ink-850 to-ink-900',
        border: 'border-red-500/40',
        textColor: 'text-red-400',
        icon: AlertTriangle,
      }
    }
    if (summary.detections_per_day > 8) {
      return {
        label: 'Alerta Moderada / Precaución',
        tone: 'warning' as const,
        badge: 'Alerta Amarilla / Precaución',
        desc: 'Actividad térmica moderada en zonas rurales y agrícolas. Se recomienda evitar quemas de rastrojo y vigilar laderas secas.',
        bg: 'from-amber-950/40 via-ink-850 to-ink-900',
        border: 'border-amber-500/40',
        textColor: 'text-amber-400',
        icon: ShieldAlert,
      }
    }
    return {
      label: 'Actividad Baja / Normal',
      tone: 'positive' as const,
      badge: 'Bajo Riesgo',
      desc: 'Pocos focos registrados en el periodo. Condiciones habituales y estables en la zona analizada.',
      bg: 'from-emerald-950/40 via-ink-850 to-ink-900',
      border: 'border-emerald-500/40',
      textColor: 'text-emerald-400',
      icon: CheckCircle2,
    }
  }, [summary])

  if (summaryState.error) {
    return <ErrorState message={summaryState.error} onRetry={summaryState.refetch} />
  }

  const isBasic = viewMode === 'basic'

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow={isBasic ? 'Monitoreo Ciudadano' : 'Telemetría Satelital Avanzada'}
        title={
          isBasic
            ? `Estado de actividad térmica · ${regionName}`
            : `Panel Analítico de Sensores & FRP · ${regionName}`
        }
        description={
          isBasic
            ? 'Información clara, resumida y comprensible para el público general sobre focos de calor satelitales en Ecuador.'
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
        /* VISTA CIUDADANA / PÚBLICO GENERAL (UX/UI OPTIMIZADA) */
        <>
          {/* 1. Diagnóstico Situacional Inmediato (Hero Card de 5 segundos) */}
          <div className={`mb-5 rounded-2xl border ${alertLevel.border} bg-gradient-to-r ${alertLevel.bg} p-4 sm:p-5 shadow-panel backdrop-blur`}>
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-start gap-3.5 max-w-3xl">
                <span className={`mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border ${alertLevel.border} bg-ink-900/80 ${alertLevel.textColor} shadow-lg`}>
                  <Flame size={22} />
                </span>
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge tone={alertLevel.tone}>{alertLevel.badge}</Badge>
                    <span className="text-xs text-slateish">
                      Territorio analizado: <strong className="text-slate-200">{regionName}</strong>
                    </span>
                  </div>
                  <h3 className="mt-1.5 text-base sm:text-lg font-bold text-white">
                    {alertLevel.label}
                  </h3>
                  <p className="mt-1 text-xs sm:text-sm text-slate-300 leading-relaxed">
                    {alertLevel.desc} {topProvince ? `La provincia con mayor atención requerida es ${topProvince.province} (${formatPercent(topProvince.share)} de los focos registrados).` : ''}
                  </p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2.5">
                <Link
                  to="/mapa"
                  className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-ink-600 bg-ink-800/80 px-3.5 py-2 text-xs font-semibold text-slate-200 transition hover:bg-ink-700 hover:text-white"
                >
                  <Compass size={14} /> Ver en Mapa
                </Link>
                <Link
                  to="/incendios"
                  className="focus-ring inline-flex items-center gap-1.5 rounded-lg bg-ember-500 px-3.5 py-2 text-xs font-bold text-slate-950 transition hover:bg-ember-400 shadow-md shadow-ember-500/20"
                >
                  <ShieldAlert size={14} /> Incendios Confirmados
                </Link>
              </div>
            </div>
          </div>

          {/* 2. Filtros de Territorio y Período (DEBAJO del diagnóstico) */}
          <FiltersBar />

          {/* 3. Tres Indicadores Vitales (Reducción de Carga Cognitiva) */}
          <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-3">
            <StatCard
              label="Focos térmicos observados"
              value={formatNumber(summary.total)}
              sub={`Promedio de ${formatDecimal(summary.detections_per_day, 1)} observaciones por día`}
              icon={Flame}
            />
            <StatCard
              label="Días con actividad térmica"
              value={`${formatNumber(summary.active_days)} días`}
              sub={`de ${formatNumber(summary.days_in_period)} días en el periodo evaluado`}
              icon={CalendarCheck2}
              accent="#3DDC97"
            />
            <StatCard
              label="Provincia con mayor registro"
              value={topProvince?.province ?? regionName}
              sub={
                topProvince
                  ? `${formatPercent(topProvince.share)} del total · Clic abajo para filtrar`
                  : 'Sin concentración provincial'
              }
              icon={MapPin}
              accent="#FFB020"
            />
          </div>

          {/* 3. Sección Central: Tendencia Mensual y Provincias Prioritarias */}
          <div className="mt-4 grid gap-4 xl:grid-cols-[1.55fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="Evolución en el Tiempo"
                title="Actividad térmica mensual registrada"
                description="Variación histórica en el territorio. Los picos suelen coincidir con épocas de sequía y vientos fuertes."
              />
              {seriesState.loading && !series ? (
                <LoadingBlock compact />
              ) : (
                <TimeSeriesChart series={series?.series ?? []} granularity="month" height={280} />
              )}
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-ink-700/60 bg-ink-800/40 p-2.5 text-[11px] text-slateish">
                <Wind size={14} className="mt-0.5 shrink-0 text-amber-400" />
                <span>
                  <strong>Estacionalidad en Ecuador:</strong> La mayor cantidad de fuegos en la Sierra y estribaciones ocurre históricamente entre <strong>agosto y noviembre</strong> debido a la baja humedad y vientos del verano andino.
                </span>
              </div>
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Territorio"
                title="Provincias con mayor atención"
                description="Haz clic en cualquier provincia para filtrar todo el panel."
              />
              <div className="space-y-2 mt-2">
                {summary.by_province.slice(0, 4).map((province, index) => {
                  const isHigh = province.share > 0.25
                  const isMedium = province.share > 0.1
                  return (
                    <button
                      key={province.province_id}
                      type="button"
                      onClick={() => update({ region: province.province_id })}
                      className="focus-ring group flex w-full flex-col gap-1.5 rounded-xl border border-ink-700/60 bg-ink-800/40 p-3 text-left transition hover:border-ember-400/50 hover:bg-ink-800/80"
                    >
                      <div className="flex items-center justify-between text-xs">
                        <span className="font-semibold text-slate-200 group-hover:text-white flex items-center gap-1.5">
                          <span className="num text-[11px] text-slateish font-bold">{index + 1}.</span>
                          {province.province}
                        </span>
                        <Badge tone={isHigh ? 'critical' : isMedium ? 'warning' : 'positive'}>
                          {isHigh ? 'Alta atención' : isMedium ? 'Atención media' : 'Normal'}
                        </Badge>
                      </div>

                      <div className="flex items-center justify-between text-[11px] text-slateish">
                        <span>Focos registrados</span>
                        <span className="num font-bold text-slate-100">{formatNumber(province.count)}</span>
                      </div>

                      <div className="h-1.5 w-full rounded-full bg-ink-700/70 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-ember-500 to-amber-400 transition-all duration-500"
                          style={{ width: `${Math.min(100, Math.max(8, province.share * 100))}%` }}
                        />
                      </div>
                    </button>
                  )
                })}
              </div>
            </Card>
          </div>

          {/* 4. Seguridad, Prevención y Reporte Ciudadano (¿Qué debo hacer?) */}
          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <div className="rounded-xl border border-red-500/30 bg-gradient-to-br from-red-950/30 to-ink-850 p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-red-400/40 bg-red-500/20 text-red-300">
                  <PhoneCall size={18} />
                </span>
                <div className="space-y-1.5 text-xs text-slate-300">
                  <p className="font-bold text-white text-sm flex items-center gap-2">
                    ¿Observas fuego activo o columnas de humo?
                  </p>
                  <p className="leading-relaxed">
                    Comunícate de inmediato al <strong>ECU 911</strong>. Indica tu cantón y puntos de referencia claros.
                    Nunca intentes combatir incendios forestales o de páramo sin equipamiento bomberil especializado.
                  </p>
                  <div className="pt-1">
                    <span className="inline-flex items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-500/15 px-3 py-1.5 font-bold text-red-200 text-xs">
                      <PhoneCall size={12} /> Línea de Emergencia: 911
                    </span>
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-xl border border-emerald-500/30 bg-gradient-to-br from-emerald-950/30 to-ink-850 p-4 shadow-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-emerald-400/40 bg-emerald-500/20 text-emerald-300">
                  <TreePine size={18} />
                </span>
                <div className="space-y-1.5 text-xs text-slate-300">
                  <p className="font-bold text-white text-sm">
                    Recomendaciones de Prevención Ciudadana
                  </p>
                  <ul className="space-y-1 text-[11px] leading-relaxed text-slateish">
                    <li>• <strong>No realizar quemas agrícolas</strong> de rastrojo en días secos o con vientos fuertes.</li>
                    <li>• <strong>Evitar fogatas</strong> y no desechar botellas de vidrio o colillas en vegetación seca.</li>
                    <li>• <strong>Un foco de calor no siempre es un incendio:</strong> puede ser quema controlada o calor industrial.</li>
                  </ul>
                </div>
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

          {/* Filtros de Telemetría Satelital */}
          <FiltersBar />

          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Detecciones de Píxel"
              value={formatNumber(summary.total)}
              sub={`${formatDecimal(summary.detections_per_day, 2)} obs/día · ${summary.active_days} días activos`}
              icon={Flame}
            />
            <StatCard
              label={sensorCardData.label}
              value={sensorCardData.value}
              sub={sensorCardData.sub}
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
