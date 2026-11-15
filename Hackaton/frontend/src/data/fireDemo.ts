import type { FilterState, Granularity, Meta, Sensor, TimeseriesPoint } from '../types/api'
import type { FireDashboard, FireEvent } from '../types/fire'

// Explicit UI fixtures, independent of the NASA dataset and the prediction model.
// Dates are anchored to the published dataset end so the default UI can be explored.
const PLACES = [
  { province: 'Loja', id: 'loja', canton: 'Quilanga', center: [-4.298, -79.405], region: 'sierra' },
  { province: 'Cotopaxi', id: 'cotopaxi', canton: 'Sigchos', center: [-0.685, -78.892], region: 'sierra' },
  { province: 'Pichincha', id: 'pichincha', canton: 'Quito', center: [0.012, -78.531], region: 'sierra' },
  { province: 'Guayas', id: 'guayas', canton: 'Daule', center: [-1.86, -79.98], region: 'costa' },
  { province: 'Imbabura', id: 'imbabura', canton: 'Pimampiro', center: [0.39, -77.94], region: 'sierra' },
  { province: 'Zamora Chinchipe', id: 'zamora-chinchipe', canton: 'Paquisha', center: [-3.931, -78.672], region: 'amazonia' },
]
const PRIORITY = { alerta_roja: 0, alerta_media: 1, quema_menor: 2 }

function periodKey(day: string, granularity: Granularity) {
  if (granularity === 'day') return day
  if (granularity === 'month') return day.slice(0, 7)
  const date = new Date(`${day}T00:00:00Z`)
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7))
  const year = date.getUTCFullYear()
  const week = Math.ceil((((date.getTime() - Date.UTC(year, 0, 1)) / 86400000) + 1) / 7)
  return `${year}-W${String(week).padStart(2, '0')}`
}

export function buildDemoDashboard(filters: FilterState, meta: Meta, granularity: Granularity): FireDashboard {
  const anchor = new Date(`${meta.date_range.end ?? '2026-11-12'}T00:00:00Z`)
  const provinces = (filters.provinces ?? '').split(',').filter(Boolean)
  const confidence = filters.confidence.split(',').filter(Boolean)
  const source = Array.from({ length: 48 }, (_, index) => {
    const place = PLACES[index % PLACES.length]
    const date = new Date(anchor)
    date.setUTCDate(date.getUTCDate() - index * 7)
    const day = date.toISOString().slice(0, 10)
    const level = index % 3 === 0 ? 'alerta_roja' : index % 3 === 1 ? 'alerta_media' : 'quema_menor'
    const sensor: Sensor = (index + Math.floor(index / 6)) % 2 === 0 ? 'VIIRS' : 'MODIS'
    const quality = ['high', 'nominal', 'low'][Math.floor(index / 6) % 3]
    const event: FireEvent = {
      id_evento: `DEMO-${String(index + 1).padStart(3, '0')}`, centro: place.center as [number, number],
      inicio: day, fin: day, nivel_alerta: level, canton: place.canton,
      province_names: [place.province], provincias: [place.id],
      frp_total: level === 'alerta_roja' ? 120 + index * 2 : level === 'alerta_media' ? 25 + index : 4,
      puntos_count: level === 'quema_menor' ? 1 : 5 + index % 14,
      nocturnas: level === 'alerta_roja' ? 1 : 0, sensores: [sensor],
      motivo_regla: 'Ejemplo de interfaz: esta clasificación no corresponde a una alerta real.',
    }
    return { event, place, sensor, quality }
  }).filter(({ place, sensor, quality }) =>
    (filters.region === 'all' || filters.region === place.region || filters.region === place.id) &&
    (provinces.length === 0 || provinces.includes(place.id)) &&
    (filters.sensor === 'all' || filters.sensor === sensor) &&
    (confidence.length === 0 || confidence.includes(quality)),
  )
  const events = source.map((row) => row.event).filter((event) => event.inicio >= filters.start && event.fin <= filters.end)
    .sort((a, b) => PRIORITY[a.nivel_alerta] - PRIORITY[b.nivel_alerta] || b.frp_total - a.frp_total)
  const byProvince = new Map<string, { id: string; name: string; count: number }>()
  const series = new Map<string, TimeseriesPoint>()
  events.forEach((event) => {
    const id = event.provincias[0]
    const province = byProvince.get(id) ?? { id, name: event.province_names[0], count: 0 }
    province.count += 1
    byProvince.set(id, province)
    const period = periodKey(event.inicio, granularity)
    const sensor = event.sensores[0] as Sensor
    const key = `${period}-${sensor}`
    const point = series.get(key) ?? { period, sensor, count: 0, frp_sum: 0, frp_mean: 0, active_days: 0 }
    point.count += event.puntos_count
    point.frp_sum = (point.frp_sum ?? 0) + event.frp_total
    point.frp_mean = point.frp_sum / point.count
    point.active_days += 1
    series.set(key, point)
  })
  const months = new Map<string, number>()
  source.forEach(({ event }) => months.set(event.inicio.slice(0, 7), (months.get(event.inicio.slice(0, 7)) ?? 0) + event.puntos_count))
  const dates = source.map(({ event }) => event.inicio).sort()
  return {
    period: { start: filters.start, end: filters.end },
    summary: { detections: events.reduce((sum, event) => sum + event.puntos_count, 0), events: events.length,
      critical_events: events.filter((event) => event.nivel_alerta === 'alerta_roja').length,
      confirmed_critical: null, extreme_risk_cantons: null, frp_total: events.reduce((sum, event) => sum + event.frp_total, 0) },
    events, by_province: [...byProvince.values()].sort((a, b) => b.count - a.count),
    series: [...series.values()].sort((a, b) => a.period.localeCompare(b.period)),
    seasonality: [...months].map(([period, count]) => ({ period, count })).sort((a, b) => a.period.localeCompare(b.period)),
    history_period: { start: dates[0] ?? null, end: dates.at(-1) ?? null },
    notes: ['Datos simulados para revisar la interfaz. No representan incendios, mediciones ni predicciones reales.'],
  }
}
