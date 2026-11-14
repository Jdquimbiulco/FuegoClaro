const numberFormatter = new Intl.NumberFormat('es-EC')

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return numberFormatter.format(value)
}

export function formatCompact(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('es-EC', { notation: 'compact', maximumFractionDigits: 1 }).format(value)
}

export function formatDecimal(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return new Intl.NumberFormat('es-EC', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value)
}

export function formatPercent(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(`${value.slice(0, 10)}T12:00:00`)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('es-EC', { day: '2-digit', month: 'short', year: 'numeric' }).format(date)
}

export function formatMonth(value: string): string {
  const [year, month] = value.split('-').map(Number)
  const date = new Date(year, (month || 1) - 1, 1)
  return new Intl.DateTimeFormat('es-EC', { month: 'long', year: 'numeric' }).format(date)
}

export function formatMonthShort(value: string): string {
  const [year, month] = value.split('-').map(Number)
  const date = new Date(year, (month || 1) - 1, 1)
  return new Intl.DateTimeFormat('es-EC', { month: 'short', year: '2-digit' }).format(date)
}

export function monthName(month: number): string {
  return new Intl.DateTimeFormat('es-EC', { month: 'long' }).format(new Date(2024, month - 1, 1))
}

export function todayIso(): string {
  return new Date().toISOString().slice(0, 10)
}

export function shiftIsoDays(iso: string, delta: number): string {
  const date = new Date(`${iso}T12:00:00`)
  date.setDate(date.getDate() + delta)
  return date.toISOString().slice(0, 10)
}

export function addMonths(month: string, delta: number): string {
  const [year, monthNumber] = month.split('-').map(Number)
  const date = new Date(year, monthNumber - 1 + delta, 1)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`
}

export function daysInMonth(month: string): number {
  const [year, monthNumber] = month.split('-').map(Number)
  return new Date(year, monthNumber, 0).getDate()
}

export function firstWeekday(month: string): number {
  const [year, monthNumber] = month.split('-').map(Number)
  const day = new Date(year, monthNumber - 1, 1).getDay()
  return (day + 6) % 7
}

export function escapeHtml(value: unknown): string {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

export function clampText(value: string, max = 70): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value
}
