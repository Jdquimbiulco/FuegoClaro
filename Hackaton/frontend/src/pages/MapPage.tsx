import type { FeatureCollection } from 'geojson'
import {
  Building2,
  Compass,
  Download,
  Layers,
  Map as MapIcon,
  MapPin,
  Satellite,
} from 'lucide-react'
import { useMemo } from 'react'
import { FiresMap } from '../components/map/FiresMap'
import { PageHeader } from '../components/layout/Layout'
import {
  Badge,
  Card,
  ErrorState,
  Notice,
  SectionHeading,
  StatCard,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { formatNumber } from '../lib/format'
import { exportUrl } from '../services/api'
import type { DetectionsResponse } from '../types/api'

const MAP_LIMIT = 20000

export default function MapPage() {
  const { meta, filters, apiPath, regionName } = useFilters()
  const detectionsState = useApi<DetectionsResponse>(
    apiPath('/detections', { limit: MAP_LIMIT, order: 'desc' }),
  )
  const geojsonState = useApi<FeatureCollection>('/regions/geojson')

  const points = detectionsState.data?.data ?? []
  const total = detectionsState.data?.pagination.total ?? 0
  const truncated = total > points.length

  const modisCount = points.filter((point) => point.sensor === 'MODIS').length
  const viirsCount = points.filter((point) => point.sensor === 'VIIRS').length

  const bbox = useMemo<[number, number, number, number] | null>(() => {
    if (filters.region === 'all') {
      if (!meta.regions.length) return null
      return meta.regions.reduce<[number, number, number, number]>(
        (acc, region) => [
          Math.min(acc[0], region.bbox[0]),
          Math.min(acc[1], region.bbox[1]),
          Math.max(acc[2], region.bbox[2]),
          Math.max(acc[3], region.bbox[3]),
        ],
        [Infinity, Infinity, -Infinity, -Infinity],
      )
    }
    const province = meta.provinces.find((item) => item.id === filters.region)
    if (province) return province.bbox
    const region = meta.regions.find((item) => item.id === filters.region)
    return region?.bbox ?? null
  }, [filters.region, meta.provinces, meta.regions])

  const highlighted = useMemo(() => {
    if (filters.region === 'all') return null
    return meta.regions.find((item) => item.id === filters.region) ??
      meta.provinces.find((item) => item.id === filters.region) ??
      null
  }, [filters.region, meta.provinces, meta.regions])

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Mapa interactivo"
        title={`Detecciones geolocalizadas · ${regionName}`}
        description="Cada marcador es una detección de foco de calor NASA FIRMS. El agrupamiento por proximidad es solo visual: no fusiona detecciones ni crea eventos. El contorno provincial es una referencia administrativa Natural Earth."
        icon={MapIcon}
        actions={
          <a
            href={exportUrl(apiPath('/export/detections.csv'))}
            className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
          >
            <Download size={14} /> Exportar detecciones
          </a>
        }
      />

      {detectionsState.error ? (
        <ErrorState message={detectionsState.error} onRetry={detectionsState.refetch} />
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="En el mapa"
              value={formatNumber(points.length)}
              sub={`de ${formatNumber(total)} detecciones filtradas`}
              icon={MapPin}
              loading={detectionsState.loading && points.length === 0}
            />
            <StatCard
              label="MODIS"
              value={formatNumber(modisCount)}
              sub="Píxeles de ~1 km · Terra/Aqua"
              icon={Satellite}
              accent="#FFB020"
            />
            <StatCard
              label="VIIRS"
              value={formatNumber(viirsCount)}
              sub="Píxeles de ~375 m · NOAA-20"
              icon={Compass}
              accent="#FF4D5E"
            />
            <StatCard
              label="Cobertura"
              value={highlighted ? 'Filtro activo' : 'Ecuador'}
              sub={
                highlighted
                  ? 'Área ajustada a la región seleccionada'
                  : `${meta.provinces.length} provincias · 4 regiones naturales`
              }
              icon={Layers}
              accent="#3DDC97"
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_300px]">
            <div>
              <FiresMap
                points={points}
                bbox={bbox}
                geojson={geojsonState.data}
                loading={detectionsState.loading}
                total={total}
              />
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slateish">
                <span>Fondo: CARTO Dark Matter · OpenStreetMap</span>
                <span className="text-ink-500">·</span>
                <span>{meta.attribution ?? 'Fuente: NASA FIRMS'}</span>
                <span className="text-ink-500">·</span>
                <span>Zoom máximo 17</span>
              </div>
            </div>

            <div className="space-y-3">
              <Card>
                <SectionHeading
                  eyebrow="Lectura del mapa"
                  title="Cómo interpretar los puntos"
                  description="La posición corresponde al centro del píxel detectado. Un mismo frente de fuego puede producir varios puntos."
                />
                <ul className="space-y-2 text-[11px] leading-relaxed text-slateish">
                  <li className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ember-400" />
                    Un punto = una detección de píxel, no un incendio confirmado.
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                    Los grupos muestran proximidad visual; el número no es un conteo de incendios.
                  </li>
                  <li className="flex gap-2">
                    <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-300" />
                    Nubes, humo y ángulo de observación pueden ocultar detecciones.
                  </li>
                </ul>
              </Card>

              <Card>
                <SectionHeading eyebrow="Resumen de capas" title="Visibilidad actual" />
                <div className="space-y-2 text-[11px]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-slate-200">
                      <span className="h-2 w-2 rounded-full bg-[#FFB020]" /> MODIS
                    </span>
                    <span className="num text-slate-100">{formatNumber(modisCount)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-slate-200">
                      <span className="h-2 w-2 rounded-full bg-[#FF4D5E]" /> VIIRS
                    </span>
                    <span className="num text-slate-100">{formatNumber(viirsCount)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="flex items-center gap-2 text-slate-200">
                      <span className="h-2 w-2 rounded-full bg-[#FF7A2F]" /> Límite provincial
                    </span>
                    <span className="text-[10px] text-slateish">Natural Earth</span>
                  </div>
                </div>
                {truncated && (
                  <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/5 p-2 text-[10px] leading-relaxed text-amber-100">
                    El mapa muestra las {formatNumber(points.length)} detecciones más recientes. Reduce el periodo o la
                    región para visualizar el conjunto completo.
                  </div>
                )}
              </Card>

              <Card>
                <SectionHeading eyebrow="Filtros" title="Vista actual" />
                <div className="space-y-1.5 text-[11px] text-slateish">
                  <p>
                    Región: <span className="text-slate-200">{regionName}</span>
                  </p>
                  <p>
                    Periodo:{' '}
                    <span className="num text-slate-200">
                      {filters.start} → {filters.end}
                    </span>
                  </p>
                  <p>
                    Sensor:{' '}
                    <span className="text-slate-200">
                      {filters.sensor === 'all' ? 'MODIS + VIIRS' : filters.sensor}
                    </span>
                  </p>
                  <p>
                    Calidad: <span className="text-slate-200">{filters.confidence || 'todas'}</span>
                  </p>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  <Badge tone="positive">Datos NASA FIRMS</Badge>
                  <Badge tone="neutral">{meta.data_mode === 'real' ? 'Dataset real' : 'Muestra'}</Badge>
                </div>
              </Card>

              {geojsonState.error && (
                <Notice tone="warning" title="Contorno no disponible">
                  No se pudo cargar el GeoJSON provincial. Las detecciones siguen visibles sobre el mapa base.
                </Notice>
              )}
              <div className="rounded-xl border border-ink-700/60 bg-ink-800/40 p-3 text-[10px] leading-relaxed text-slateish">
                <p className="mb-1 flex items-center gap-1 font-semibold text-slate-200">
                  <Building2 size={11} /> Atribución
                </p>
                NASA FIRMS · MODIS Collection 6.1 · VIIRS 375 m. Límites: Natural Earth 1:10m. Fondo: CARTO/OSM.
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
