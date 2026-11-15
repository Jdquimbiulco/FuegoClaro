import { useCallback, useEffect, useState } from 'react'
import { apiGet, ApiError, withQuery } from '../services/api'
import { buildDemoDashboard } from '../data/fireDemo'
import type { ApiEnvelope, FilterState, Granularity, Meta } from '../types/api'
import type { FireDashboard } from '../types/fire'

interface Result { key: string; data: FireDashboard | null; demo: boolean; error: string | null }

export function useFireDashboard(filters: FilterState, meta: Meta, granularity: Granularity) {
  const [result, setResult] = useState<Result | null>(null)
  const [nonce, setNonce] = useState(0)
  const refetch = useCallback(() => setNonce((value) => value + 1), [])
  const path = withQuery('/fire-events', {
    start_date: filters.start, end_date: filters.end, region_id: filters.region,
    sensor: filters.sensor, confidence: filters.confidence, province_ids: filters.provinces, granularity,
  })
  const key = `${path}:${meta.dataset_version}:${nonce}`
  useEffect(() => {
    const controller = new AbortController()
    apiGet<ApiEnvelope<FireDashboard>>(path, controller.signal).then((payload) => {
      if (!controller.signal.aborted) setResult({ key, data: payload.data, demo: false, error: null })
    }).catch((failure: unknown) => {
      if (controller.signal.aborted) return
      if (failure instanceof ApiError && failure.status === 404) {
        setResult({ key, data: buildDemoDashboard(filters, meta, granularity), demo: true, error: null })
      } else {
        setResult({ key, data: null, demo: false, error: failure instanceof Error ? failure.message : 'No se pudieron cargar los eventos.' })
      }
    })
    return () => controller.abort()
  }, [filters, meta, granularity, path, key])
  const current = result?.key === key ? result : null
  return { data: current?.data ?? null, loading: !current, error: current?.error ?? null, demo: current?.demo ?? false, refetch }
}
