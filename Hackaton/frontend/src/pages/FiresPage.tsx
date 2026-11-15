import { useEffect, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { AlertTriangle, Flame, MapPin, Radio, RefreshCw, ShieldAlert } from 'lucide-react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { PageHeader } from '../components/layout/Layout'
import { FiltersBar } from '../components/layout/FiltersBar'
import { Badge, Card, EmptyState, ErrorState, LoadingBlock, SectionHeading, StatCard } from '../components/ui/Primitives'
import { TimeSeriesChart } from '../components/charts/Charts'
import { useFilters } from '../context/FiltersContext'
import { useFireDashboard } from '../hooks/useFireDashboard'
import { ProvinceMultiSelect } from '../components/layout/ProvinceMultiSelect'
import { formatDate, formatDecimal, formatNumber } from '../lib/format'
import type { Granularity } from '../types/api'
import type { AlertLevel, FireDashboard, FireEvent } from '../types/fire'

const LEVELS = {
  alerta_roja: { label: 'Crítico', tone: 'critical', color: '#FF4D5E' },
  alerta_media: { label: 'Moderado', tone: 'warning', color: '#FF8A34' },
  quema_menor: { label: 'Bajo', tone: 'warning', color: '#FACC15' },
} as const
const MONTHS = ['Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun', 'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic']
const control = 'focus-ring rounded-lg border border-ink-600 bg-ink-900 px-3 py-2 text-xs text-slate-100'

function mapLink(event: FireEvent, search: string, demo: boolean) {
  const params = new URLSearchParams(search)
  params.set('start', event.inicio)
  params.set('end', event.fin)
  params.set('focus_lat', String(event.centro[0]))
  params.set('focus_lon', String(event.centro[1]))
  params.set('event', event.id_evento)
  params.set('region', event.provincias[0] ?? 'all')
  params.delete('provinces')
  if (demo) params.set('demo_event', '1')
  else params.delete('demo_event')
  return `/mapa?${params.toString()}`
}

function Seasonality({ data }: { data: FireDashboard }) {
  const years = [...new Set(data.seasonality.map((item) => item.period.slice(0, 4)))]
  const values = new Map(data.seasonality.map((item) => [item.period, item.count]))
  const max = Math.max(1, ...data.seasonality.map((item) => item.count))
  const { update } = useFilters()
  return (
    <Card>
      <SectionHeading eyebrow="Estacionalidad" title="Actividad térmica por año y mes"
        description="Histórico disponible con los mismos filtros territoriales, de sensor y confianza. Selecciona un mes para analizarlo. El color representa detecciones registradas." />
      {years.length === 0 ? <EmptyState title="Sin histórico para estos filtros" /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[580px] border-separate border-spacing-1 text-center text-xs">
            <caption className="sr-only">Conteos mensuales de detecciones por año</caption>
            <thead><tr><th scope="col" className="text-slateish">Año</th>{MONTHS.map((month) => <th scope="col" key={month} className="pb-2 font-medium text-slateish">{month}</th>)}</tr></thead>
            <tbody>{years.map((year) => <tr key={year}>
              <th scope="row" className="pr-2 font-medium text-slate-200">{year}</th>
              {MONTHS.map((month, index) => {
                const period = `${year}-${String(index + 1).padStart(2, '0')}`
                const value = values.get(period)
                return <td key={period}><button type="button" disabled={value === undefined}
                  className="focus-ring h-10 w-full rounded-md border border-ink-700 text-[10px] text-white transition hover:border-ember-300 disabled:cursor-default disabled:opacity-30"
                  style={{ backgroundColor: value === undefined || value === 0 ? '#142033' : `rgba(255, 92, 22, ${0.18 + 0.72 * Math.sqrt(value / max)})` }}
                  aria-label={`${month} ${year}: ${value === undefined ? 'fuera del histórico disponible' : `${value} detecciones. Analizar mes`}`}
                  title={`${month} ${year}: ${value === undefined ? 'Sin cobertura en el histórico' : `${formatNumber(value)} detecciones`}`}
                  onClick={() => update({ start: `${period}-01`, end: `${period}-${new Date(Number(year), index + 1, 0).getDate()}` })}>
                  {value === undefined ? '—' : formatNumber(value)}
                </button></td>
              })}
            </tr>)}</tbody>
          </table>
        </div>
      )}
      <p className="mt-3 text-[11px] text-slateish">Cobertura de registros: {formatDate(data.history_period.start)} — {formatDate(data.history_period.end)}. Los meses de los extremos pueden estar incompletos.</p>
    </Card>
  )
}

export default function FiresPage() {
  const { regionName, filters, update, meta } = useFilters()
  const { search } = useLocation()
  const [granularity, setGranularity] = useState<Granularity>('month')
  const [severity, setSeverity] = useState<'all' | AlertLevel>('all')
  const [page, setPage] = useState({ key: '', count: 20 })
  const [autoRefresh, setAutoRefresh] = useState(false)
  const state = useFireDashboard(filters, meta, granularity)
  const { refetch } = state
  useEffect(() => {
    if (!autoRefresh) return
    const timer = window.setInterval(() => { if (!document.hidden) refetch() }, 60000)
    return () => window.clearInterval(timer)
  }, [autoRefresh, refetch])
  const pageKey = `${search}:${severity}`
  const visible = page.key === pageKey ? page.count : 20
  const data = state.data
  const priority = { alerta_roja: 0, alerta_media: 1, quema_menor: 2 }
  const events = data?.events.filter((event) => severity === 'all' || event.nivel_alerta === severity)
    .sort((a, b) => priority[a.nivel_alerta] - priority[b.nivel_alerta] || b.frp_total - a.frp_total) ?? []

  return (
    <div className="animate-fade-up">
      <PageHeader eyebrow="Centro de mando" title={`Incendios y alertas · ${regionName}`}
        description="Explora los eventos térmicos del periodo, prioriza su revisión y consulta la evidencia en el mapa."
        icon={ShieldAlert} actions={<button type="button" className={control} disabled={state.loading} onClick={refetch}><RefreshCw size={14} className="mr-2 inline" />Actualizar</button>} />
      <FiltersBar demonstration={state.demo} />
      <div className="mb-4"><ProvinceMultiSelect /></div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <label className="text-xs text-slateish">Sensor <select aria-label="Sensor de eventos" className={control} value={filters.sensor} onChange={(event) => update({ sensor: event.target.value as typeof filters.sensor })}><option value="all">Ambos sensores</option><option>MODIS</option><option>VIIRS</option></select></label>
        <label className="text-xs text-slateish">Confianza <select aria-label="Confianza de eventos" className={control} value={filters.confidence} onChange={(event) => update({ confidence: event.target.value })}><option value="">Todos los niveles</option><option value="high">Alta</option><option value="nominal,high">Nominal y alta</option><option value="low">Baja</option><option value="nominal">Nominal</option><option value="unknown">Sin clasificar</option></select></label>
        <label className="ml-auto flex items-center gap-2 text-xs text-slateish"><input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} className="accent-orange-500" />Consultar actualizaciones cada minuto</label>
      </div>
      <p className="mb-4 text-xs text-slateish">{state.demo ? 'Vista de demostración' : meta.data_mode === 'sample' ? 'Muestra de datos' : 'Dataset'} · Último registro disponible: {formatDate(meta.date_range.end)}. La consulta automática revisa el dataset publicado; no es una transmisión en vivo.</p>
      {state.demo && !state.loading && <div role="status" className="mb-4 rounded-xl border border-amber-400/40 bg-amber-500/10 p-4 text-sm text-amber-100"><strong>Datos de demostración.</strong> El servicio de eventos todavía no está disponible. Las tarjetas y gráficos siguientes usan ejemplos simulados para revisar la interfaz; no son alertas reales ni predicciones del modelo.</div>}
      {state.error ? <ErrorState message={state.error} onRetry={refetch} /> : state.loading ? <LoadingBlock label="Calculando eventos e indicadores del periodo…" /> : data ? <>
        <div className="mb-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Total focos detectados" value={formatNumber(data.summary.detections)} sub={`${formatNumber(data.summary.events)} eventos agrupados`} icon={Flame} />
          <StatCard label="Alertas críticas calculadas" value={formatNumber(data.summary.critical_events)} sub="Priorización por reglas del algoritmo" icon={AlertTriangle} accent="#FF4D5E" />
          <StatCard label="Críticos confirmados" value={data.summary.confirmed_critical === null ? 'Sin datos' : formatNumber(data.summary.confirmed_critical)} sub="Pendiente de confirmación en campo" icon={ShieldAlert} accent="#FFB020" />
          <StatCard label="Cantones en riesgo extremo" value={data.summary.extreme_risk_cantons === null ? 'Sin datos' : formatNumber(data.summary.extreme_risk_cantons)} sub="Pendiente del modelo de susceptibilidad" icon={MapPin} accent="#3DDC97" />
        </div>
        <div className="grid items-start gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
          <Card>
            <SectionHeading eyebrow="Revisión prioritaria" title="Feed de alertas" description="Eventos del periodo ordenados por severidad y, dentro de cada nivel, por FRP." />
            <label className="mb-3 block text-xs text-slateish">Mostrar severidad
              <select className={`${control} mt-1 w-full`} value={severity} onChange={(event) => setSeverity(event.target.value as typeof severity)}>
                <option value="all">Todos los niveles</option>{Object.entries(LEVELS).map(([value, level]) => <option key={value} value={value}>{level.label}</option>)}
              </select>
            </label>
            <p className="mb-3 text-xs text-slateish">{formatNumber(events.length)} eventos · FRP total del periodo: {formatDecimal(data.summary.frp_total, 1)} MW</p>
            <div className="max-h-[820px] space-y-3 overflow-y-auto pr-1">
              {events.length === 0 ? <EmptyState title="Sin eventos para esta selección" description="Prueba otro periodo, territorio o nivel de severidad." /> : events.slice(0, visible).map((event) => {
                const level = LEVELS[event.nivel_alerta]
                return <article key={event.id_evento} className="rounded-xl border border-ink-700 border-l-[3px] bg-ink-850 p-3" style={{ borderLeftColor: level.color }}>
                  <div className="flex items-center justify-between gap-2"><h3 className="text-xs font-semibold text-white">{event.id_evento}</h3><Badge tone={level.tone}>{level.label}</Badge></div>
                  <p className="mt-2 text-sm font-medium text-slate-100">{event.province_names.join(' · ') || 'Provincia sin asignar'}</p>
                  <p className="mt-1 text-[11px] text-slateish">Cantón: {event.canton ?? 'no disponible'} · {event.sensores.join(' / ')}</p>
                  <div className="my-3 grid grid-cols-2 gap-2 text-xs"><div><p className="text-slateish">FRP total</p><strong className="text-white">{formatDecimal(event.frp_total, 1)} MW</strong></div><div><p className="text-slateish">Focos agrupados</p><strong className="text-white">{formatNumber(event.puntos_count)}</strong></div></div>
                  <p className="text-[11px] text-slateish">{formatDate(event.inicio)} — {formatDate(event.fin)} · fecha local</p>
                  <details className="mt-2 text-[11px] text-slateish"><summary className="cursor-pointer">Criterio de clasificación</summary><p className="mt-1">{event.motivo_regla}</p></details>
                  <Link className="focus-ring mt-3 inline-flex items-center gap-2 rounded-lg border border-ember-400/30 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-200" to={mapLink(event, search, state.demo)}><MapPin size={13} />Ver en mapa</Link>
                </article>
              })}
              {events.length > visible && <button type="button" className={`${control} w-full`} onClick={() => setPage({ key: pageKey, count: visible + 20 })}>Mostrar 20 más</button>}
            </div>
          </Card>
          <div className="min-w-0 space-y-4">
            <Card>
              <SectionHeading eyebrow="Comparación temporal" title="MODIS vs VIIRS" description="Detecciones del periodo seleccionado, desglosadas por sensor." action={<select aria-label="Agrupación temporal" className={control} value={granularity} onChange={(event) => setGranularity(event.target.value as Granularity)}><option value="day">Diaria</option><option value="week">Semanal</option><option value="month">Mensual</option></select>} />
              <TimeSeriesChart series={data.series} granularity={granularity} />
            </Card>
            <Card>
              <SectionHeading eyebrow="Distribución territorial" title="Provincias con más eventos" description="Un evento que abarca varias provincias se cuenta en cada una de ellas. Selecciona una barra para filtrar." />
              {data.by_province.length === 0 ? <EmptyState title="Sin eventos por provincia" /> : <div className="h-72"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.by_province.slice(0, 10)} layout="vertical" margin={{ left: 4, right: 20 }}>
                <CartesianGrid stroke="#1B2A3F" horizontal={false} /><XAxis type="number" allowDecimals={false} tick={{ fill: '#8EA3BE', fontSize: 11 }} /><YAxis dataKey="name" type="category" width={125} tick={{ fill: '#CBD5E1', fontSize: 10 }} />
                <Tooltip contentStyle={{ background: '#0B1320', border: '1px solid #1B2A3F', color: '#fff' }} />
                <Bar dataKey="count" name="Eventos" fill="#FF7A2F" radius={[0, 4, 4, 0]} cursor="pointer" onClick={(entry) => { if (entry.id) update({ region: 'all', provinces: entry.id }) }} />
              </BarChart></ResponsiveContainer></div>}
            </Card>
            <Seasonality data={data} />
            <div className="flex items-start gap-2 rounded-xl border border-ink-700 p-3 text-xs text-slateish"><Radio size={16} className="shrink-0 text-ember-300" /><p>Las categorías priorizan la revisión de eventos térmicos. La confirmación de un incendio y su estado actual requieren información adicional a estas detecciones.</p></div>
          </div>
        </div>
      </> : <EmptyState title="No hay información de eventos disponible" />}
    </div>
  )
}
