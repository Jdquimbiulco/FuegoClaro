import test from 'node:test'
import assert from 'node:assert/strict'
import { buildDemoDashboard } from '../src/data/fireDemo.ts'

const meta = { date_range: { start: '2022-01-01', end: '2026-11-12' } }
const base = { start: '2025-11-13', end: '2026-11-12', region: 'all', sensor: 'all', confidence: '', provinces: '' }

test('KPIs, chart series and feed remain consistent', () => {
  const data = buildDemoDashboard(base, meta, 'month')
  assert.equal(data.summary.events, data.events.length)
  assert.equal(data.summary.detections, data.events.reduce((n, event) => n + event.puntos_count, 0))
  assert.equal(data.summary.detections, data.series.reduce((n, point) => n + point.count, 0))
  assert.equal(data.summary.events, data.by_province.reduce((n, point) => n + point.count, 0))
  assert.equal(data.summary.confirmed_critical, null)
  assert.equal(data.summary.extreme_risk_cantons, null)
  const priority = { alerta_roja: 0, alerta_media: 1, quema_menor: 2 }
  for (let i = 1; i < data.events.length; i++) {
    const prev = data.events[i - 1], next = data.events[i]
    assert.ok(priority[prev.nivel_alerta] <= priority[next.nivel_alerta])
    if (prev.nivel_alerta === next.nivel_alerta) assert.ok(prev.frp_total >= next.frp_total)
  }
})

test('province multiselect intersects with sensor and confidence', () => {
  const data = buildDemoDashboard({ ...base, provinces: 'loja,guayas', sensor: 'VIIRS', confidence: 'high' }, meta, 'day')
  assert.ok(data.events.length > 0)
  assert.ok(data.events.every((event) => ['loja', 'guayas'].includes(event.provincias[0]) && event.sensores[0] === 'VIIRS'))
  assert.ok(data.events.length < buildDemoDashboard({ ...base, provinces: 'loja,guayas' }, meta, 'day').events.length)
})

test('date range filters feed but keeps historical heatmap', () => {
  const all = buildDemoDashboard(base, meta, 'week')
  const month = buildDemoDashboard({ ...base, start: '2026-11-01' }, meta, 'week')
  assert.ok(month.events.length < all.events.length)
  assert.ok(month.events.every((event) => event.inicio >= '2026-11-01'))
  assert.deepEqual(month.seasonality, all.seasonality)
  assert.ok(month.series.every((point) => /^\d{4}-W\d{2}$/.test(point.period)))
})

test('empty selections do not fabricate zero-valued confirmations', () => {
  const data = buildDemoDashboard({ ...base, provinces: 'galapagos' }, meta, 'month')
  assert.equal(data.summary.events, 0)
  assert.equal(data.summary.detections, 0)
  assert.deepEqual(data.events, [])
  assert.equal(data.history_period.start, null)
  assert.equal(data.summary.confirmed_critical, null)
})
