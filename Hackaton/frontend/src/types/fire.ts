import type { TimeseriesPoint } from './api'

export type AlertLevel = 'alerta_roja' | 'alerta_media' | 'quema_menor'
export interface FireEvent {
  id_evento: string
  centro: [number, number]
  inicio: string
  fin: string
  nivel_alerta: AlertLevel
  motivo_regla: string
  provincias: string[]
  province_names: string[]
  canton: string | null
  frp_total: number
  puntos_count: number
  nocturnas: number
  sensores: string[]
}
export interface FireDashboard {
  period: { start: string; end: string }
  summary: {
    detections: number
    events: number
    critical_events: number
    confirmed_critical: number | null
    extreme_risk_cantons: number | null
    frp_total: number
  }
  events: FireEvent[]
  by_province: { id: string; name: string; count: number }[]
  series: TimeseriesPoint[]
  seasonality: { period: string; count: number }[]
  history_period: { start: string | null; end: string | null }
  notes: string[]
}
