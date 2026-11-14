export type Sensor = 'MODIS' | 'VIIRS'
export type ConfidenceLevel = 'low' | 'nominal' | 'high' | 'unknown'
export type DataMode = 'real' | 'sample' | 'empty'
export type Granularity = 'day' | 'week' | 'month'

export interface DateRange {
  start: string | null
  end: string | null
}

export interface Region {
  id: string
  name: string
  description: string
  bbox: [number, number, number, number]
  center: [number, number]
  provinces: string[]
  count?: number
}

export interface Province {
  id: string
  iso: string
  name: string
  region_id: string
  region: string
  bbox: [number, number, number, number]
  center: [number, number]
  count?: number
}

export interface Meta {
  app: string
  version: string
  data_mode: DataMode
  dataset_version: string | null
  generated_at: string | null
  date_range: DateRange
  default_window: { start: string; end: string }
  by_sensor: Record<string, number>
  date_by_sensor: Record<string, { start: string; end: string; count: number }>
  sensors: { id: Sensor; name: string; description: string }[]
  products: string[]
  confidence_levels: ConfidenceLevel[]
  regions: Region[]
  provinces: Province[]
  attribution: string | null
  source: string | null
  limitations: string[]
  warnings: string[]
  records: Record<string, unknown>
}

export interface FilterState {
  start: string
  end: string
  region: string
  sensor: 'all' | Sensor
  confidence: string
}

export interface Detection {
  id: string
  sensor: Sensor
  satellite: string
  instrument: string
  source_product: string
  latitude: number
  longitude: number
  acq_date: string
  acq_time: string
  acq_date_local: string
  acq_time_local: string
  acquired_at_utc: string
  daynight: string
  confidence_level: ConfidenceLevel
  confidence_raw: string
  confidence_score: number | null
  frp: number | null
  brightness: number | null
  bright_t31: number | null
  bright_ti5: number | null
  scan: number | null
  track: number | null
  version: string
  type: string
  province: string
  province_id: string
  region: string
  region_id: string
  provenance_id: string
}

export interface ApiMeta {
  data_mode: DataMode
  dataset_version: string | null
  generated_at: string | null
  period: { start: string; end: string }
  filters: Record<string, unknown>
  attribution: string
  notes: string[]
}

export interface Pagination {
  total: number
  limit: number
  offset: number
  returned: number
  truncated: boolean
}

export interface DetectionsResponse {
  meta: ApiMeta
  pagination: Pagination
  data: Detection[]
}

export interface SensorSummary {
  sensor: Sensor
  count: number
  share: number
  active_days: number
  frp_sum: number | null
  frp_mean: number | null
}

export interface RegionSummary {
  region_id: string
  region: string
  count: number
  share: number
}

export interface ProvinceSummary {
  province_id: string
  province: string
  region_id: string
  count: number
  share: number
}

export interface Summary {
  period: { start: string; end: string; days: number }
  region: { id: string; name: string }
  sensor_filter: string
  total: number
  active_days: number
  days_in_period: number
  detections_per_day: number
  by_sensor: SensorSummary[]
  by_confidence: Record<string, number>
  by_region: RegionSummary[]
  by_province: ProvinceSummary[]
  by_daynight: Record<string, number>
  frp: { sum: number | null; mean: number | null; max: number | null; valid: number }
  date_range: DateRange
  notes: string[]
}

export interface TimeseriesPoint {
  period: string
  sensor: Sensor
  count: number
  frp_sum: number | null
  frp_mean: number | null
  active_days: number
}

export interface Timeseries {
  granularity: Granularity
  period: { start: string; end: string }
  series: TimeseriesPoint[]
  totals_by_sensor: Record<string, number>
  notes: string[]
}

export interface CalendarDay {
  date: string
  day: number
  total: number
  by_sensor: Record<string, number>
  intensity: number
}

export interface CalendarData {
  month: string
  start: string
  end: string
  days: CalendarDay[]
  max_daily: number
  total: number
  notes: string[]
}

export interface SensorComparison {
  sensor: Sensor
  count: number
  share: number
  active_days: number
  coverage: number
  mean_daily: number
  max_daily: number
  frp_sum: number | null
  frp_mean: number | null
  confidence: Record<string, number>
  satellites: { satellite: string; count: number }[]
  products: { product: string; count: number }[]
}

export interface Comparison {
  period: { start: string; end: string; days: number }
  region: { id: string; name: string }
  total: number
  by_sensor: SensorComparison[]
  by_region: { region_id: string; region: string; sensor: Sensor; count: number }[]
  series: TimeseriesPoint[]
  granularity: Granularity
  count_ratio: { viirs_over_modis: number; interpretation: string } | null
  notes: string[]
}

export interface Anomaly {
  date: string
  region_id: string
  region: string
  sensor: Sensor
  observed: number
  baseline_mean: number
  baseline_std: number
  baseline_days: number
  baseline_years: number[]
  baseline_dates_sample: string[]
  z_score: number
  p_value: number
  q_value: number
  direction: 'high' | 'low' | 'none'
}

export interface AnomaliesData {
  analysis_period: { start: string; end: string }
  region: { id: string; name: string }
  sensor_filter: string
  method: string
  parameters: Record<string, unknown>
  summary: {
    tests: number
    candidates: number
    flagged: number
    high_anomalies: number
    low_anomalies: number
    regions_affected: string[]
    max_abs_z: number | null
  }
  anomalies: Anomaly[]
  notes: string[]
}

export interface Insight {
  id: string
  title: string
  text: string
  tone: 'info' | 'warning' | 'critical' | 'positive'
  indicator: string
  value: string
  method: string
  evidence: { label: string; value: string }[]
  caveat: string
  region: { id: string; name: string }
  period: { start: string; end: string; days?: number }
  sensor: string
}

export interface InsightsData {
  summary: { total: number; generated: number; anomalies_flagged?: number }
  period: { start: string; end: string; days: number }
  region: { id: string; name: string }
  insights: Insight[]
  notes: string[]
  method: string
}

export interface ProvenanceResponse {
  data_mode: DataMode
  loaded_at: string
  path: string | null
  manifest: {
    dataset_version?: string
    generated_at?: string
    source?: string
    attribution?: string
    requested_period?: { start: string; end: string }
    sources?: { source_product: string; sensor: string; label: string; start: string; end: string; records: number }[]
    records?: Record<string, unknown>
    transformations?: string[]
    limitations?: string[]
    file?: { path: string; sha256: string; bytes: number }
    [key: string]: unknown
  }
}

export interface ApiEnvelope<T> {
  meta: ApiMeta
  data: T
}
