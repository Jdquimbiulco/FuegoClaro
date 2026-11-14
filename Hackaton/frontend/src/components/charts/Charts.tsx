import { useMemo } from 'react'
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Anomaly, RegionSummary, SensorSummary, TimeseriesPoint } from '../../types/api'
import { CONFIDENCE_COLORS, CONFIDENCE_LABELS, SENSOR_COLORS } from '../../lib/constants'
import { formatCompact, formatDate, formatMonthShort, formatNumber, formatPercent } from '../../lib/format'

const tooltipStyle = {
  background: '#0B1320',
  border: '1px solid #1B2A3F',
  borderRadius: 10,
  fontSize: 12,
  color: '#E8EFF9',
}

function periodLabel(period: string, granularity?: string): string {
  if (granularity === 'month' || /^\d{4}-\d{2}$/.test(period)) return formatMonthShort(period)
  if (granularity === 'day' || /^\d{4}-\d{2}-\d{2}$/.test(period)) return formatDate(period)
  return period
}

export function TimeSeriesChart({
  series,
  granularity = 'month',
  height = 280,
}: {
  series: TimeseriesPoint[]
  granularity?: string
  height?: number
}) {
  const data = useMemo(() => {
    const map = new Map<string, { period: string; MODIS?: number; VIIRS?: number }>()
    series.forEach((point) => {
      const row = map.get(point.period) ?? { period: point.period }
      row[point.sensor] = (row[point.sensor] ?? 0) + point.count
      map.set(point.period, row)
    })
    return Array.from(map.values()).sort((a, b) => a.period.localeCompare(b.period))
  }, [series])

  if (!data.length) {
    return <div className="flex h-[220px] items-center justify-center text-xs text-slateish">Sin datos para la serie temporal.</div>
  }

  return (
    <div style={{ height }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="modisFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SENSOR_COLORS.MODIS} stopOpacity={0.28} />
              <stop offset="100%" stopColor={SENSOR_COLORS.MODIS} stopOpacity={0.02} />
            </linearGradient>
            <linearGradient id="viirsFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={SENSOR_COLORS.VIIRS} stopOpacity={0.28} />
              <stop offset="100%" stopColor={SENSOR_COLORS.VIIRS} stopOpacity={0.02} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#1B2A3F" />
          <XAxis
            dataKey="period"
            tickFormatter={(value: string) => periodLabel(value, granularity)}
            tick={{ fill: '#8EA3BE', fontSize: 10 }}
            tickLine={false}
            axisLine={{ stroke: '#1B2A3F' }}
            minTickGap={24}
          />
          <YAxis
            tick={{ fill: '#8EA3BE', fontSize: 10 }}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: number) => formatCompact(value)}
            width={52}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            labelFormatter={(value) => periodLabel(String(value), granularity)}
            formatter={(value, name) => [formatNumber(Number(value)), String(name)]}
          />
          <Legend wrapperStyle={{ fontSize: 11, color: '#8EA3BE' }} iconType="circle" iconSize={7} />
          <Area
            type="monotone"
            dataKey="MODIS"
            stroke={SENSOR_COLORS.MODIS}
            strokeWidth={1.8}
            fill="url(#modisFill)"
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls
          />
          <Area
            type="monotone"
            dataKey="VIIRS"
            stroke={SENSOR_COLORS.VIIRS}
            strokeWidth={1.8}
            fill="url(#viirsFill)"
            dot={false}
            activeDot={{ r: 3 }}
            connectNulls
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

export function ConfidenceDonut({ values }: { values: Record<string, number> }) {
  const data = Object.entries(values)
    .filter(([, value]) => value > 0)
    .map(([key, value]) => ({ key, name: CONFIDENCE_LABELS[key] ?? key, value }))
  const total = data.reduce((sum, item) => sum + item.value, 0)

  if (!total) {
    return <div className="flex h-[190px] items-center justify-center text-xs text-slateish">Sin desglose de confianza.</div>
  }

  return (
    <div className="flex items-center gap-2">
      <div className="relative h-[170px] w-[170px] shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={76} paddingAngle={2} stroke="none">
              {data.map((item) => (
                <Cell key={item.key} fill={CONFIDENCE_COLORS[item.key] ?? '#475569'} />
              ))}
            </Pie>
            <Tooltip contentStyle={tooltipStyle} formatter={(value) => [formatNumber(Number(value)), 'Detecciones']} />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="num text-lg font-semibold text-white">{formatCompact(total)}</span>
          <span className="text-[9px] uppercase tracking-wider text-slateish">total</span>
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-1.5">
        {data.map((item) => (
          <li key={item.key} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="flex items-center gap-1.5 text-slateish">
              <span className="h-2 w-2 rounded-full" style={{ background: CONFIDENCE_COLORS[item.key] }} />
              {item.name}
            </span>
            <span className="num text-slate-200">
              {formatNumber(item.value)} <span className="text-slateish">({formatPercent(item.value / total)})</span>
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}

export function SensorSplit({ sensors }: { sensors: SensorSummary[] }) {
  const total = sensors.reduce((sum, item) => sum + item.count, 0)
  if (!total) return <div className="py-8 text-center text-xs text-slateish">Sin detecciones por sensor.</div>
  return (
    <div className="space-y-4">
      <div className="flex h-3 overflow-hidden rounded-full bg-ink-800">
        {sensors.map((item) => (
          <div
            key={item.sensor}
            style={{ width: `${item.share * 100}%`, background: SENSOR_COLORS[item.sensor] }}
            title={`${item.sensor}: ${formatNumber(item.count)}`}
          />
        ))}
      </div>
      {sensors.map((item) => (
        <div key={item.sensor} className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full" style={{ background: SENSOR_COLORS[item.sensor] }} />
            <span className="text-xs font-medium text-slate-200">{item.sensor}</span>
            <span className="text-[10px] text-slateish">{item.active_days} días activos</span>
          </div>
          <div className="text-right">
            <p className="num text-sm font-semibold text-white">{formatNumber(item.count)}</p>
            <p className="text-[10px] text-slateish">{formatPercent(item.share)} del total</p>
          </div>
        </div>
      ))}
    </div>
  )
}

export function RegionBars({ regions, onSelect }: { regions: RegionSummary[]; onSelect?: (id: string) => void }) {
  const max = regions.reduce((value, item) => Math.max(value, item.count), 0)
  if (!regions.length) return <div className="py-8 text-center text-xs text-slateish">Sin regiones para mostrar.</div>
  return (
    <div className="space-y-2">
      {regions.slice(0, 6).map((region) => (
        <button
          key={region.region_id}
          type="button"
          onClick={() => onSelect?.(region.region_id)}
          className="focus-ring group w-full text-left"
        >
          <div className="mb-1 flex items-center justify-between text-[11px]">
            <span className="text-slate-200 group-hover:text-white">{region.region}</span>
            <span className="num text-slateish">
              {formatNumber(region.count)} <span className="text-[10px]">({formatPercent(region.share)})</span>
            </span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-ink-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-ember-600 to-ember-400 transition-all group-hover:from-ember-500 group-hover:to-amber-300"
              style={{ width: `${max ? (region.count / max) * 100 : 0}%` }}
            />
          </div>
        </button>
      ))}
    </div>
  )
}

export function AnomalyBars({ anomalies }: { anomalies: Anomaly[] }) {
  const data = anomalies.slice(0, 12).map((item) => ({
    label: `${item.date.slice(5)} · ${item.region} · ${item.sensor}`,
    observed: item.observed,
    baseline: item.baseline_mean,
    direction: item.direction,
  }))
  if (!data.length) {
    return <div className="flex h-[240px] items-center justify-center text-xs text-slateish">Sin anomalías que graficar.</div>
  }
  return (
    <div className="h-[320px]">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 12, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#1B2A3F" />
          <XAxis type="number" tick={{ fill: '#8EA3BE', fontSize: 10 }} tickLine={false} axisLine={false} />
          <YAxis
            type="category"
            dataKey="label"
            width={160}
            tick={{ fill: '#A9BBD2', fontSize: 9 }}
            tickLine={false}
            axisLine={false}
          />
          <Tooltip contentStyle={tooltipStyle} formatter={(value, name) => [formatNumber(Number(value)), String(name)]} />
          <Legend wrapperStyle={{ fontSize: 11, color: '#8EA3BE' }} iconSize={7} />
          <Bar dataKey="observed" name="Observado" radius={[0, 3, 3, 0]} fill={SENSOR_COLORS.VIIRS} barSize={7} />
          <Bar dataKey="baseline" name="Media histórica" radius={[0, 3, 3, 0]} fill="#334155" barSize={7} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
