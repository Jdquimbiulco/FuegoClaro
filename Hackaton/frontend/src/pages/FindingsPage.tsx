import {
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  Download,
  Flame,
  Gauge,
  GitCompareArrows,
  Lightbulb,
  Map as MapIcon,
  Sparkles,
} from 'lucide-react'
import { useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
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
import { formatDate, formatNumber } from '../lib/format'
import { exportUrl } from '../services/api'
import type { ApiEnvelope, Insight, InsightsData, Timeseries } from '../types/api'

const TONE_STYLES: Record<
  Insight['tone'],
  { border: string; background: string; text: string; label: string }
> = {
  info: {
    border: 'border-sky-400/25',
    background: 'bg-sky-400/5',
    text: 'text-sky-200',
    label: 'Informativo',
  },
  warning: {
    border: 'border-amber-400/30',
    background: 'bg-amber-400/5',
    text: 'text-amber-200',
    label: 'Precaución',
  },
  critical: {
    border: 'border-rose-400/30',
    background: 'bg-rose-400/5',
    text: 'text-rose-200',
    label: 'Relevante',
  },
  positive: {
    border: 'border-emerald-400/30',
    background: 'bg-emerald-400/5',
    text: 'text-emerald-200',
    label: 'Positivo',
  },
}

const RELATED_ROUTES: Record<string, { to: string; label: string; icon: typeof MapIcon }> = {
  volumen: { to: '/mapa', label: 'Explorar en el mapa', icon: MapIcon },
  brecha_sensores: { to: '/comparador', label: 'Ver comparador', icon: GitCompareArrows },
  pico_temporal: { to: '/calendario', label: 'Ver calendario', icon: CalendarDays },
  concentracion_regional: { to: '/mapa', label: 'Ver regiones', icon: MapIcon },
  confianza: { to: '/comparador', label: 'Comparar confianza', icon: GitCompareArrows },
  frp: { to: '/mapa', label: 'Ver detecciones', icon: MapIcon },
}

function InsightCard({ insight, compact = false }: { insight: Insight; compact?: boolean }) {
  const tone = TONE_STYLES[insight.tone] ?? TONE_STYLES.info
  const related = RELATED_ROUTES[insight.id]
  const evidence = compact ? insight.evidence.slice(0, 2) : insight.evidence

  return (
    <article className={`flex flex-col rounded-2xl border ${tone.border} ${tone.background} p-4`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={`flex items-center gap-1 text-[9px] font-semibold uppercase tracking-[0.16em] ${tone.text}`}>
            <Lightbulb size={11} />
            {tone.label} · {insight.indicator}
          </p>
          <h3 className="mt-1 line-clamp-2 text-sm font-semibold leading-snug text-white">{insight.title}</h3>
        </div>
        <span
          className={`num shrink-0 rounded-xl border ${tone.border} bg-ink-900/50 px-2.5 py-1.5 text-xl font-semibold ${tone.text}`}
        >
          {insight.value}
        </span>
      </div>

      {evidence.length > 0 && (
        <div className={`mt-3 grid gap-1.5 ${compact ? 'grid-cols-2' : 'grid-cols-2 sm:grid-cols-4'}`}>
          {evidence.map((item) => (
            <div
              key={`${insight.id}-${item.label}`}
              className="rounded-lg border border-ink-700/60 bg-ink-900/40 px-2 py-1.5"
            >
              <p className="num text-xs font-semibold text-slate-100">{item.value}</p>
              <p className="line-clamp-1 text-[9px] uppercase tracking-wider text-slateish">{item.label}</p>
            </div>
          ))}
        </div>
      )}

      {!compact && (
        <details className="group mt-3 border-t border-ink-700/60 pt-2">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-[10px] font-semibold text-slateish transition hover:text-slate-200">
            <span>Lectura, método y límite</span>
            <ChevronDown size={12} className="transition group-open:rotate-180" />
          </summary>
          <div className="mt-2 space-y-1.5">
            <p className="text-[10px] leading-relaxed text-slate-200/85">{insight.text}</p>
            <p className="text-[10px] leading-relaxed text-slateish">
              <span className="font-semibold text-slate-300">Método:</span> {insight.method}
            </p>
            <p className="text-[10px] leading-relaxed text-amber-100/70">
              <span className="font-semibold">Límite:</span> {insight.caveat}
            </p>
          </div>
        </details>
      )}

      {related && (
        <div className="mt-auto pt-3">
          <Link
            to={related.to}
            className={`focus-ring inline-flex items-center gap-1 text-[10px] font-semibold ${tone.text} transition hover:opacity-80`}
          >
            {related.label} <ArrowUpRight size={11} />
          </Link>
        </div>
      )}
    </article>
  )
}

export default function FindingsPage() {
  const { meta, apiPath, regionName, viewMode, setViewMode } = useFilters()
  const isBasic = viewMode === 'basic'
  const insightsState = useApi<ApiEnvelope<InsightsData>>(apiPath('/insights'))
  const data = insightsState.data?.data
  const location = useLocation()
  const seriesState = useApi<ApiEnvelope<Timeseries>>(
    apiPath('/stats/timeseries', { granularity: 'month' }),
  )
  const series = seriesState.data?.data

  useEffect(() => {
    if (location.hash !== '#anomalias') return
    let target: HTMLElement | null = null
    let observer: ResizeObserver | null = null
    let stopTimer = 0

    const jump = () => {
      target?.scrollIntoView({ behavior: 'auto', block: 'start' })
    }

    const startTimer = window.setTimeout(() => {
      target = document.getElementById('anomalias')
      if (!target) return
      jump()
      observer = new ResizeObserver(jump)
      observer.observe(target)
      stopTimer = window.setTimeout(() => observer?.disconnect(), 3000)
    }, 150)

    return () => {
      window.clearTimeout(startTimer)
      window.clearTimeout(stopTimer)
      observer?.disconnect()
    }
  }, [location.hash, data])

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Hallazgos"
        title={`Hallazgos del periodo · ${regionName}`}
        description={
          isBasic
            ? 'Los patrones más relevantes, con cifras verificables.'
            : 'Hallazgos deterministas sobre detecciones y anomalías.'
        }
        icon={Sparkles}
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
              <Download size={14} /> Descargar evidencia
            </a>
          )
        }
      />

      {insightsState.error ? (
        <ErrorState message={insightsState.error} onRetry={insightsState.refetch} />
      ) : insightsState.loading && !data ? (
        <LoadingBlock label="Construyendo hallazgos a partir de los datos…" />
      ) : !data ? (
        <Card>
          <EmptyState
            title="No hay hallazgos para los filtros actuales"
            description="Ajusta el periodo, la región o la calidad."
          />
        </Card>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-3">
            <StatCard
              label="Detecciones"
              value={formatNumber(data.summary.total)}
              sub={`${formatNumber(data.period.days)} días analizados`}
              icon={Flame}
              accent="#FF5C16"
            />
            <StatCard
              label="Hallazgos"
              value={formatNumber(data.summary.generated)}
              sub="Patrones detectados"
              icon={Sparkles}
              accent="#FFB020"
            />
            <StatCard
              label="Periodo"
              value={`${formatNumber(data.period.days)} d`}
              sub={`${formatDate(data.period.start)} → ${formatDate(data.period.end)}`}
              icon={CalendarDays}
              accent="#3DDC97"
            />
          </div>

          <Card className="mb-4">
            <SectionHeading
              eyebrow="Tendencia"
              title="Detecciones por mes"
              description="Mismo periodo y filtros."
            />
            {seriesState.loading && !series ? (
              <LoadingBlock compact />
            ) : (
              <TimeSeriesChart series={series?.series ?? []} granularity="month" height={180} />
            )}
          </Card>

          <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
            <p className="eyebrow">Hallazgos del periodo</p>
            {!isBasic && (
              <div className="flex flex-wrap gap-1.5">
                <Badge tone="positive">Sin cifras inventadas</Badge>
                <Badge tone="neutral">Determinista</Badge>
                <Badge tone="neutral">{meta.data_mode === 'real' ? 'Datos reales' : 'Muestra'}</Badge>
              </div>
            )}
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            {data.insights.length === 0 ? (
              <Card className="xl:col-span-2">
                <EmptyState
                  title="No hay hallazgos para los filtros actuales"
                  description="Ajusta el periodo, la región o la calidad."
                />
              </Card>
            ) : (
              data.insights.map((insight) => (
                <InsightCard key={insight.id} insight={insight} compact={isBasic} />
              ))
            )}

            
          </div>
        </>
      )}
    </div>
  )
}
