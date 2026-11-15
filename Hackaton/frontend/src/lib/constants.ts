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

export interface QualityOption {
  value: string
  label: string
  shortLabel: string
  badge: string
  badgeTone: 'neutral' | 'ember' | 'positive' | 'warning'
  description: string
  technicalDetails: string
}

export const QUALITY_OPTIONS: QualityOption[] = [
  {
    value: '',
    label: 'Todas las confianzas',
    shortLabel: 'Todas',
    badge: 'Exhaustivo',
    badgeTone: 'neutral',
    description: 'Incluye el 100% de las detecciones satelitales (baja, nominal y alta).',
    technicalDetails: 'Sin filtros de calidad. Útil para investigación completa, pero puede contener calor industrial, ruido térmico o reflejos solares.',
  },
  {
    value: 'nominal,high',
    label: 'Nominal y alta',
    shortLabel: 'Nominal+',
    badge: 'Recomendado NASA',
    badgeTone: 'ember',
    description: 'Estándar operativo recomendado por NASA para monitoreo de incendios.',
    technicalDetails: 'Filtra falsos positivos por nubes, agua o reflejos de superficie. En MODIS confianza ≥ 30%; en VIIRS categorías nominal y high.',
  },
  {
    value: 'high',
    label: 'Solo alta',
    shortLabel: 'Alta',
    badge: 'Certeza máxima',
    badgeTone: 'positive',
    description: 'Máxima certeza algorítmica y condiciones atmosféricas óptimas.',
    technicalDetails: 'En MODIS confianza ≥ 80%; en VIIRS píxeles intensos sin interferencias. Probabilidad casi nula de error, ideal para alertas críticas.',
  },
  {
    value: 'low',
    label: 'Solo baja',
    shortLabel: 'Baja',
    badge: 'Baja certeza',
    badgeTone: 'warning',
    description: 'Detecciones dudosas, de baja intensidad o con nubosidad parcial.',
    technicalDetails: 'En MODIS confianza < 30%; en VIIRS categoría low. Útil para estudiar inicios de fuego o bajo nubes, pero con mayor tasa de falsos positivos.',
  },
]

export const DISCLAIMER =
  'Una detección de foco de calor no es un incendio confirmado ni una medida de superficie quemada. Los conteos dependen de la resolución, sensibilidad y condiciones de observación de cada sensor.'
