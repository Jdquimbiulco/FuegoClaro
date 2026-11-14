import {
  ArrowUpRight,
  BookOpenCheck,
  Download,
  GitCompareArrows,
  Lightbulb,
  Map as MapIcon,
  Microscope,
  Sparkles,
} from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/layout/Layout'
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  Notice,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { formatNumber } from '../lib/format'
import { exportUrl } from '../services/api'
import type { ApiEnvelope, Insight, InsightsData } from '../types/api'

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
  pico_temporal: { to: '/calendario', label: 'Ver calendario', icon: BookOpenCheck },
  concentracion_regional: { to: '/mapa', label: 'Ver regiones', icon: MapIcon },
  confianza: { to: '/comparador', label: 'Comparar confianza', icon: GitCompareArrows },
  anomalia: { to: '/anomalias', label: 'Abrir radar', icon: Microscope },
  frp: { to: '/mapa', label: 'Ver detecciones', icon: MapIcon },
}

function InsightCard({ insight }: { insight: Insight }) {
  const tone = TONE_STYLES[insight.tone] ?? TONE_STYLES.info
  const related = RELATED_ROUTES[insight.id]
  return (
    <article className={`rounded-2xl border ${tone.border} ${tone.background} p-4`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <span className={`mt-0.5 rounded-lg border px-1.5 py-1 ${tone.border} ${tone.text}`}>
            <Lightbulb size={14} />
          </span>
          <div>
            <p className={`text-[9px] font-semibold uppercase tracking-[0.16em] ${tone.text}`}>
              {tone.label} · {insight.indicator}
            </p>
            <h3 className="mt-0.5 text-sm font-semibold leading-snug text-white">{insight.title}</h3>
          </div>
        </div>
        <span className={`num rounded-lg border ${tone.border} bg-ink-900/40 px-2 py-1 text-xs font-semibold ${tone.text}`}>
          {insight.value}
        </span>
      </div>

      <p className="mt-2 text-[11px] leading-relaxed text-slate-200/90">{insight.text}</p>

      <div className="mt-3 grid gap-1.5 sm:grid-cols-2">
        {insight.evidence.map((item) => (
          <div
            key={`${insight.id}-${item.label}`}
            className="flex items-center justify-between gap-2 rounded-lg border border-ink-700/60 bg-ink-900/30 px-2 py-1"
          >
            <span className="text-[10px] text-slateish">{item.label}</span>
            <span className="num text-[10px] font-semibold text-slate-100">{item.value}</span>
          </div>
        ))}
      </div>

      <div className="mt-3 space-y-1 border-t border-ink-700/60 pt-2">
        <p className="text-[10px] leading-relaxed text-slateish">
          <span className="font-semibold text-slate-300">Método:</span> {insight.method}
        </p>
        <p className="text-[10px] leading-relaxed text-amber-100/70">
          <span className="font-semibold">Límite:</span> {insight.caveat}
        </p>
      </div>

      {related && (
        <Link
          to={related.to}
          className={`focus-ring mt-3 inline-flex items-center gap-1 text-[10px] font-semibold ${tone.text} transition hover:opacity-80`}
        >
          {related.label} <ArrowUpRight size={11} />
        </Link>
      )}
    </article>
  )
}

export default function FindingsPage() {
  const { meta, apiPath, regionName } = useFilters()
  const insightsState = useApi<ApiEnvelope<InsightsData>>(apiPath('/insights'))
  const data = insightsState.data?.data

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Centro de hallazgos"
        title={`Hallazgos trazables · ${regionName}`}
        description="Cada hallazgo se construye con plantillas deterministas sobre agregaciones, comparación y anomalías ya calculadas. No se usa un modelo generativo para inventar cifras ni conclusiones."
        icon={Sparkles}
        actions={
          <a
            href={exportUrl(apiPath('/export/detections.csv'))}
            className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
          >
            <Download size={14} /> Descargar evidencia
          </a>
        }
      />

      {insightsState.error ? (
        <ErrorState message={insightsState.error} onRetry={insightsState.refetch} />
      ) : insightsState.loading && !data ? (
        <LoadingBlock label="Construyendo hallazgos a partir de los datos…" />
      ) : !data || data.insights.length === 0 ? (
        <Card>
          <EmptyState
            title="No hay hallazgos para los filtros actuales"
            description="Los hallazgos solo se generan cuando existen detecciones y agregaciones suficientes. Ajusta el periodo, la región o la calidad."
          />
        </Card>
      ) : (
        <>
          <div className="mb-4 grid gap-3 md:grid-cols-[1fr_1fr_1.2fr]">
            <Card>
              <p className="eyebrow">Hallazgos generados</p>
              <p className="num mt-1 text-2xl font-semibold text-white">{formatNumber(data.summary.generated)}</p>
              <p className="mt-1 text-[10px] leading-relaxed text-slateish">
                A partir de {formatNumber(data.summary.total)} detecciones en el periodo filtrado.
              </p>
            </Card>
            <Card>
              <p className="eyebrow">Anomalías marcadas</p>
              <p className="num mt-1 text-2xl font-semibold text-white">
                {formatNumber(data.summary.anomalies_flagged ?? 0)}
              </p>
              <p className="mt-1 text-[10px] leading-relaxed text-slateish">
                Con el detector y control FDR configurados por defecto.
              </p>
            </Card>
            <Card>
              <p className="eyebrow">Regla de generación</p>
              <p className="mt-1 text-[11px] leading-relaxed text-slate-200">{data.method}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <Badge tone="positive">Sin cifras inventadas</Badge>
                <Badge tone="neutral">Determinista</Badge>
                <Badge tone="neutral">{meta.data_mode === 'real' ? 'Datos reales' : 'Muestra'}</Badge>
              </div>
            </Card>
          </div>

          <div className="grid gap-3 xl:grid-cols-2">
            {data.insights.map((insight) => (
              <InsightCard key={insight.id} insight={insight} />
            ))}
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Notice tone="info" title="Trazabilidad" icon={BookOpenCheck}>
              Cada tarjeta muestra indicador, valor, evidencia, método y límite. El CSV exportado contiene las
              detecciones subyacentes con su producto de origen y su identificador de procedencia.
            </Notice>
            <Notice tone="warning" title="Esto no es un diagnóstico de incendios" icon={Microscope}>
              Los hallazgos describen patrones en detecciones de píxeles. No confirman incendios, no estiman superficie
              quemada y no sustituyen la validación en campo ni los productos oficiales de área quemada.
            </Notice>
          </div>

          <p className="mt-4 text-[10px] leading-relaxed text-slateish">
            {data.notes.join(' ')} Periodo: {data.period.start} → {data.period.end}. Región: {data.region.name}.
          </p>
        </>
      )}
    </div>
  )
}
