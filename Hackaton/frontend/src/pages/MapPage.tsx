import type { FeatureCollection, Geometry } from 'geojson'
import {
  Building2,
  Compass,
  Download,
  Gauge,
  Layers,
  Map as MapIcon,
  MapPin,
  PhoneCall,
  Satellite,
  ShieldAlert,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { FiresMap } from '../components/map/FiresMap'
import { PageHeader } from '../components/layout/Layout'
import { FiltersBar } from '../components/layout/FiltersBar'
import {
  Card,
  ErrorState,
  Notice,
  SectionHeading,
  StatCard,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { formatNumber } from '../lib/format'
import { exportUrl, withQuery } from '../services/api'
import type { ApiEnvelope, DetectionsResponse, EnvironmentalAlertsData, ProtectedAreaProperties, SusceptibilityMapData } from '../types/api'
import type { MapLayers } from '../components/map/FiresMap'

const MAP_LIMIT = 20000

export default function MapPage() {
  const [params] = useSearchParams()
  const focus = useMemo(() => {
    const lat = Number(params.get('focus_lat'))
    const lon = Number(params.get('focus_lon'))
    if (!params.get('focus_lat') || !params.get('focus_lon') || !Number.isFinite(lat) || !Number.isFinite(lon) || Math.abs(lat) > 90 || Math.abs(lon) > 180) return null
    return { coordinates: [lat, lon] as [number, number], name: params.get('event') || 'Evento seleccionado', demo: params.get('demo_event') === '1' }
  }, [params])
  const { meta, filters, apiPath, regionName, viewMode, setViewMode } = useFilters()
  const [riskHorizon, setRiskHorizon] = useState(7)
  const [layers, setLayers] = useState<MapLayers>({ detections: true, risk: true, protectedAreas: true, alerts: true })
  const detectionsState = useApi<DetectionsResponse>(
    apiPath('/detections', { limit: MAP_LIMIT, order: 'desc' }),
  )
  const geojsonState = useApi<FeatureCollection>('/regions/geojson')
  const riskState = useApi<ApiEnvelope<SusceptibilityMapData>>(
    layers.risk ? withQuery('/susceptibility', { level: 'cell', window_days: riskHorizon }) : null,
  )
  const protectedAreasState = useApi<ApiEnvelope<FeatureCollection<Geometry, ProtectedAreaProperties>>>('/protected-areas')
  const alertsState = useApi<ApiEnvelope<EnvironmentalAlertsData>>(
    layers.alerts ? apiPath('/environmental-alerts', { window_days: riskHorizon }) : null,
  )

  const points = detectionsState.data?.data ?? []
  const total = detectionsState.data?.pagination.total ?? 0
  const truncated = total > points.length
  const riskGeojson = useMemo<FeatureCollection | null>(() => {
    const payload = riskState.data?.data
    return payload ? { type: 'FeatureCollection', features: payload.features } : null
  }, [riskState.data])
  const protectedAreasGeojson = protectedAreasState.data?.data ?? null
  const alerts = alertsState.data?.data.alerts ?? []

  const modisCount = points.filter((point) => point.sensor === 'MODIS').length
  const viirsCount = points.filter((point) => point.sensor === 'VIIRS').length

  const bbox = useMemo<[number, number, number, number] | null>(() => {
    const canton = meta.cantons.find((item) => item.id === filters.canton)
    if (canton) return canton.bbox
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
  }, [filters.canton, filters.region, meta.cantons, meta.provinces, meta.regions])

  const highlighted = useMemo(() => {
    const canton = meta.cantons.find((item) => item.id === filters.canton)
    if (canton) return canton
    if (filters.region === 'all') return null
    return meta.regions.find((item) => item.id === filters.region) ??
      meta.provinces.find((item) => item.id === filters.region) ??
      null
  }, [filters.canton, filters.region, meta.cantons, meta.provinces, meta.regions])

  const isBasic = viewMode === 'basic'

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow={isBasic ? 'Mapa Ciudadano' : 'Mapa interactivo'}
        title={
          isBasic
            ? `Mapa de actividad térmica · ${regionName}`
            : `Detecciones geolocalizadas · ${regionName}`
        }
        description={
          isBasic
            ? 'Exploración geográfica de focos de calor satelitales en Ecuador. Usa los controles para acercar tu cantón o provincia.'
            : 'Cada marcador es una detección de foco de calor NASA FIRMS. El agrupamiento por proximidad es solo visual: no fusiona detecciones ni crea eventos. El contorno provincial es una referencia administrativa Natural Earth.'
        }
        icon={MapIcon}
        actions={
          <div className="flex items-center gap-2">
            {isBasic ? (
              <button
                type="button"
                onClick={() => setViewMode('expert')}
                className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20"
              >
                <Gauge size={14} /> Vista Analítica
              </button>
            ) : (
              <a
                href={exportUrl(apiPath('/export/detections.csv'))}
                className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
              >
                <Download size={14} /> Exportar detecciones
              </a>
            )}
          </div>
        }
      />

      {/* Feed operacional: las alertas se recalculan, no se persisten. */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-ember-400/30 bg-gradient-to-r from-ember-500/15 via-ember-500/10 to-transparent p-3 text-xs">
        <div className="flex items-center gap-2.5 text-slate-200">
          <ShieldAlert size={16} className="text-ember-400 shrink-0" />
          <span><strong>{alerts.length}</strong> alertas ambientales priorizadas para el horizonte predictivo de {riskHorizon} días.</span>
        </div>
        <span className="text-slateish">Cruza riesgo predictivo y áreas protegidas; no representa incendios confirmados.</span>
      </div>

      <FiltersBar />

      {detectionsState.error ? (
        <ErrorState message={detectionsState.error} onRetry={detectionsState.refetch} />
      ) : (
        <>
          <div className="relative z-10 mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="En el mapa"
              value={formatNumber(points.length)}
              sub={`de ${formatNumber(total)} detecciones filtradas`}
              icon={MapPin}
              loading={detectionsState.loading && points.length === 0}
            />
            <StatCard
              label={isBasic ? 'Satélite MODIS' : 'MODIS'}
              value={formatNumber(modisCount)}
              sub={isBasic ? 'Sensor de amplia cobertura (~1 km)' : 'Píxeles de ~1 km · Terra/Aqua'}
              icon={Satellite}
              accent="#FFB020"
            />
            <StatCard
              label={isBasic ? 'Satélite VIIRS' : 'VIIRS'}
              value={formatNumber(viirsCount)}
              sub={isBasic ? 'Sensor de alta resolución (~375 m)' : 'Píxeles de ~375 m · NOAA-20'}
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

          <div className="grid gap-4">
            <div>
              {focus && <div className="mb-2 rounded-lg border border-amber-400/30 bg-amber-500/10 p-3 text-xs text-amber-100">{focus.demo ? 'Ubicación de demostración' : 'Evento seleccionado'}: {focus.name}. El marcador amarillo identifica el centro del evento.</div>}
              <FiresMap
                focus={focus}
                points={points}
                bbox={bbox}
                geojson={geojsonState.data}
                loading={detectionsState.loading}
                total={total}
                riskGeojson={riskGeojson}
                protectedAreasGeojson={protectedAreasGeojson}
                alerts={alerts}
                layers={layers}
                onLayerChange={(key, value) => setLayers((current) => ({ ...current, [key]: value }))}
                riskHorizon={riskHorizon}
                onRiskHorizonChange={setRiskHorizon}
                alertsLoading={alertsState.loading}
              />
              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slateish">
                <span>Fondo cartográfico: Esri World Canvas / Satellite / Topo (Sin marcas de agua)</span>
                <span className="text-ink-500">·</span>
                <span>{meta.attribution ?? 'Fuente: NASA FIRMS'}</span>
                <span className="text-ink-500">·</span>
                <span>Zoom con rueda o controles inferiores</span>
              </div>
            </div>

            <div className="space-y-3">
              {isBasic ? (
                /* SIDEBAR BÁSICA */
                <>
                  <Card>
                    <SectionHeading
                      eyebrow="Lectura Rápida"
                      title="¿Cómo leer este mapa?"
                      description="Guía sencilla de interpretación de puntos."
                    />
                    <ul className="space-y-2.5 text-xs leading-relaxed text-slateish mt-2">
                      <li className="flex items-start gap-2">
                        <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-[#FF4D5E]" />
                        <span>
                          <strong className="text-white">Puntos rojos y amarillos:</strong> Lugares donde el satélite detectó temperatura anormal en la superficie.
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-amber-400" />
                        <span>
                          <strong className="text-white">Círculos con números:</strong> Agrupan puntos cercanos para facilitar la visualización. Al hacer clic se expanden.
                        </span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-sky-400" />
                        <span>
                          <strong className="text-white">Nubes y humo:</strong> Pueden ocultar fuegos en el momento exacto en que pasa el satélite.
                        </span>
                      </li>
                    </ul>
                  </Card>

                  <Card>
                    <SectionHeading eyebrow="Riesgo y ambiente" title="Alertas dinámicas" description="Cruce de riesgo predictivo y eventos críticos con el Sistema Nacional de Áreas Protegidas." />
                    <div className="space-y-2 text-xs text-slateish">
                      <p><span className="font-semibold text-white">{alerts.length}</span> alertas prioritarias para el horizonte de {riskHorizon} días.</p>
                      <p>Las alertas no se almacenan: se recalculan con la capa de riesgo publicada.</p>
                      {alerts.slice(0, 3).map((alert) => <div key={alert.id} className="rounded-lg border border-ember-400/30 bg-ember-500/10 p-2 text-ember-100"><strong>{alert.protected_area.name}</strong><br />{alert.title}</div>)}
                      {riskState.error && <p className="text-amber-200">Capa predictiva no disponible: {riskState.error}</p>}
                      {alertsState.error && <p className="text-amber-200">Alertas no disponibles: {alertsState.error}</p>}
                    </div>
                  </Card>

                  <Card>
                    <SectionHeading eyebrow="Emergencias" title="Protocolo de Alerta" />
                    <div className="space-y-2 text-xs text-slateish">
                      <p>
                        Si observas humo denso o fuego activo fuera de control en tu localidad:
                      </p>
                      <div className="flex items-center gap-2 rounded-lg border border-red-500/30 bg-red-500/10 p-2.5 text-red-200">
                        <PhoneCall size={16} className="shrink-0" />
                        <span className="font-bold">Llama inmediatamente al 911</span>
                      </div>
                      <p className="text-[11px]">
                        No intentes acercarte ni realizar quemas en días con viento fuerte.
                      </p>
                    </div>
                  </Card>

                  <Card>
                    <SectionHeading eyebrow="Modo Analista" title="¿Eres especialista?" />
                    <p className="text-xs text-slateish leading-relaxed">
                      Para ver desglose de píxeles scan/track, confianza numérica (0-100) y clasificaciones de satélite:
                    </p>
                    <button
                      type="button"
                      onClick={() => setViewMode('expert')}
                      className="mt-3 focus-ring inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-sky-400/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20"
                    >
                      <Gauge size={13} /> Activar Modo Experto
                    </button>
                  </Card>
                </>
              ) : (
                /* SIDEBAR EXPERTA */
                <>
                  <Card>
                    <SectionHeading
                      eyebrow="Interpretación Técnica"
                      title="Geometría & Píxeles de Detección"
                      description="La posición corresponde al baricentro del píxel detectado por el sensor durante la pasada orbital."
                    />
                    <ul className="space-y-2 text-[11px] leading-relaxed text-slateish">
                      <li className="flex gap-2">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-ember-400" />
                        <span>
                          <strong className="text-white">Detección puntual:</strong> Corresponde a una anomalía de radiancia térmica infrarroja (bandas de 4 µm y 11 µm), no a un incendio delimitado.
                        </span>
                      </li>
                      <li className="flex gap-2">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                        <span>
                          <strong className="text-white">Clusters numéricos:</strong> Agrupamiento dinámico Leaflet para rendimiento visual; al ampliar zoom se disuelven en sus píxeles individuales.
                        </span>
                      </li>
                      <li className="flex gap-2">
                        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-sky-300" />
                        <span>
                          <strong className="text-white">Factores de oclusión:</strong> Nubosidad espesa, plumas de humo denso o paso fuera de nadir pueden ocultar calor activo.
                        </span>
                      </li>
                    </ul>
                  </Card>

                  <Card>
                    <SectionHeading eyebrow="Resolución Espacial" title="Desglose por Sensor" />
                    <div className="space-y-2.5 text-[11px]">
                      <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-1.5 font-semibold text-slate-200">
                            <span className="h-2 w-2 rounded-full bg-[#FFB020]" /> MODIS (Terra/Aqua)
                          </span>
                          <span className="num font-bold text-slate-100">{formatNumber(modisCount)}</span>
                        </div>
                        <p className="mt-0.5 text-[10px] text-slateish">
                          Píxel ~1,000 m en nadir · Histórico desde 2000
                        </p>
                      </div>

                      <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2">
                        <div className="flex items-center justify-between">
                          <span className="flex items-center gap-1.5 font-semibold text-slate-200">
                            <span className="h-2 w-2 rounded-full bg-[#FF4D5E]" /> VIIRS (NOAA-20 / S-NPP)
                          </span>
                          <span className="num font-bold text-slate-100">{formatNumber(viirsCount)}</span>
                        </div>
                        <p className="mt-0.5 text-[10px] text-slateish">
                          Píxel ~375 m en bandas I · Mayor detección nocturna
                        </p>
                      </div>

                      <div className="flex items-center justify-between gap-2 px-1 text-[10px] text-slateish">
                        <span className="flex items-center gap-1.5">
                          <span className="h-1.5 w-1.5 rounded-full bg-[#FF7A2F]" /> Límites: Natural Earth 1:10m
                        </span>
                        <span className="text-slate-300">WGS84 EPSG:4326</span>
                      </div>
                    </div>
                    {truncated && (
                      <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/5 p-2 text-[10px] leading-relaxed text-amber-100">
                        El mapa renderiza las {formatNumber(points.length)} detecciones más recientes para optimizar WebGL/Leaflet.
                      </div>
                    )}
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
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

