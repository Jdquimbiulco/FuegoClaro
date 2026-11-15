import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import type { FilterState, Meta } from '../types/api'
import { withQuery } from '../services/api'

export type ViewMode = 'basic' | 'expert'

interface FiltersContextValue {
  meta: Meta
  filters: FilterState
  viewMode: ViewMode
  setViewMode: (mode: ViewMode) => void
  toggleViewMode: () => void
  update: (patch: Partial<FilterState>) => void
  setDay: (day: string) => void
  reset: () => void
  apiPath: (path: string, extra?: Record<string, string | number | boolean | null | undefined>) => string
  regionName: string
  activeFilterCount: number
}

const FiltersContext = createContext<FiltersContextValue | null>(null)

export function FiltersProvider({ meta, children }: { meta: Meta; children: ReactNode }) {
  const [searchParams, setSearchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()

  const [viewMode, setViewModeState] = useState<ViewMode>(() => {
    return 'expert'
  })

  const setViewMode = useCallback((mode: ViewMode) => {
    // Se conserva la firma para compatibilidad con vistas históricas; la
    // aplicación opera exclusivamente en modo experto.
    void mode
    setViewModeState('expert')
  }, [])

  const toggleViewMode = useCallback(() => {
    setViewMode(viewMode === 'basic' ? 'expert' : 'basic')
  }, [viewMode, setViewMode])

  const filters: FilterState = useMemo(
    () => ({
      start: searchParams.get('start') || meta.default_window.start,
      end: searchParams.get('end') || meta.default_window.end,
      region: searchParams.get('region') || 'all',
      sensor: (searchParams.get('sensor') as FilterState['sensor']) || 'all',
      confidence: searchParams.get('confidence') || '',
      provinces: searchParams.get('provinces') || '',
      canton: searchParams.get('canton') || '',
    }),
    [meta.default_window.end, meta.default_window.start, searchParams],
  )

  useEffect(() => {
    const next = new URLSearchParams(searchParams)
    let changed = false
    if (!next.get('start')) {
      next.set('start', meta.default_window.start)
      changed = true
    }
    if (!next.get('end')) {
      next.set('end', meta.default_window.end)
      changed = true
    }
    if (changed) {
      navigate(
        { pathname: location.pathname, search: next.toString(), hash: location.hash },
        { replace: true },
      )
    }
  }, [
    location.hash,
    location.pathname,
    meta.default_window.end,
    meta.default_window.start,
    navigate,
    searchParams,
  ])

  const write = useCallback(
    (next: FilterState) => {
      const params = new URLSearchParams(searchParams)
      params.set('start', next.start)
      params.set('end', next.end)
      params.set('region', next.region)
      params.set('sensor', next.sensor)
      if (next.confidence) params.set('confidence', next.confidence)
      else params.delete('confidence')
      if (next.provinces) params.set('provinces', next.provinces)
      else params.delete('provinces')
      if (next.canton) params.set('canton', next.canton)
      else params.delete('canton')
      setSearchParams(params, { replace: true })
    },
    [searchParams, setSearchParams],
  )

  const update = useCallback(
    (patch: Partial<FilterState>) => {
      const merged = { ...filters, ...patch }
      if (merged.start > merged.end) {
        if (patch.start) merged.end = merged.start
        else merged.start = merged.end
      }
      write(merged)
    },
    [filters, write],
  )

  const setDay = useCallback(
    (day: string) => {
      write({ ...filters, start: day, end: day })
    },
    [filters, write],
  )

  const reset = useCallback(() => {
    write({
      start: meta.default_window.start,
      end: meta.default_window.end,
      region: 'all',
      sensor: 'all',
      confidence: '',
      provinces: '',
      canton: '',
    })
  }, [meta.default_window.end, meta.default_window.start, write])

  const regionName = useMemo(() => {
    if (filters.canton) {
      const canton = meta.cantons.find((item) => item.id === filters.canton)
      if (canton) return `${canton.name} · ${canton.province}`
    }
    if (filters.region === 'all') return 'Ecuador'
    const natural = meta.regions.find((region) => region.id === filters.region)
    if (natural) return natural.name
    const province = meta.provinces.find((item) => item.id === filters.region)
    if (province) return province.name
    return filters.region
  }, [filters.canton, filters.region, meta.cantons, meta.provinces, meta.regions])

  const activeFilterCount = useMemo(() => {
    let count = 0
    if (filters.region !== 'all') count += 1
    if (filters.sensor !== 'all') count += 1
    if (filters.confidence) count += 1
    if (filters.provinces) count += 1
    if (filters.canton) count += 1
    if (
      filters.start !== meta.default_window.start ||
      filters.end !== meta.default_window.end
    ) {
      count += 1
    }
    return count
  }, [filters, meta.default_window.end, meta.default_window.start])

  const apiPath = useCallback(
    (path: string, extra: Record<string, string | number | boolean | null | undefined> = {}) =>
      withQuery(path, {
        start_date: filters.start,
        end_date: filters.end,
        region_id: filters.region,
        sensor: filters.sensor,
        confidence: filters.confidence,
        canton_id: filters.canton,
        ...extra,
      }),
    [filters],
  )

  const value = useMemo(
    () => ({
      meta,
      filters,
      viewMode,
      setViewMode,
      toggleViewMode,
      update,
      setDay,
      reset,
      apiPath,
      regionName,
      activeFilterCount,
    }),
    [
      meta,
      filters,
      viewMode,
      setViewMode,
      toggleViewMode,
      update,
      setDay,
      reset,
      apiPath,
      regionName,
      activeFilterCount,
    ],
  )

  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>
}

export function useFilters(): FiltersContextValue {
  const context = useContext(FiltersContext)
  if (!context) throw new Error('useFilters debe usarse dentro de FiltersProvider')
  return context
}
