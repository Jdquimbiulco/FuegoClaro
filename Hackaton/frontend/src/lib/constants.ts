import type { Sensor } from '../types/api'

export const SENSOR_COLORS: Record<Sensor, string> = {
  MODIS: '#FFB020',
  VIIRS: '#FF4D5E',
}

export const SENSOR_LABELS: Record<Sensor, string> = {
  MODIS: 'MODIS · ~1 km',
  VIIRS: 'VIIRS · ~375 m',
}

export const CONFIDENCE_LABELS: Record<string, string> = {
  low: 'Baja',
  nominal: 'Nominal',
  high: 'Alta',
  unknown: 'Sin dato',
}

export const CONFIDENCE_COLORS: Record<string, string> = {
  low: '#64748B',
  nominal: '#FFB020',
  high: '#3DDC97',
  unknown: '#475569',
}

export const QUALITY_OPTIONS = [
  { value: '', label: 'Todas las confianzas' },
  { value: 'nominal,high', label: 'Nominal y alta' },
  { value: 'high', label: 'Solo alta' },
  { value: 'low', label: 'Solo baja' },
]

export const DISCLAIMER =
  'Una detección de foco de calor no es un incendio confirmado ni una medida de superficie quemada. Los conteos dependen de la resolución, sensibilidad y condiciones de observación de cada sensor.'
