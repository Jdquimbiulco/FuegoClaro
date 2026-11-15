import L from 'leaflet'
import 'leaflet.markercluster'
import { Flame, Maximize2, Moon, Mountain, Satellite } from 'lucide-react'
import { useEffect, useState } from 'react'
import type { Feature, FeatureCollection } from 'geojson'
import { CircleMarker, Popup, GeoJSON, MapContainer, ScaleControl, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import type { Detection, EnvironmentalAlert } from '../../types/api'
import { CONFIDENCE_LABELS, SENSOR_COLORS } from '../../lib/constants'
import { escapeHtml, formatDecimal, formatNumber } from '../../lib/format'

type BasemapMode = 'dark' | 'satellite' | 'topo'
export type MapLayers = { detections: boolean; risk: boolean; protectedAreas: boolean; alerts: boolean }

const BASEMAPS: Record<
  BasemapMode,
  {
    name: string
    icon: typeof Moon
    url: string
    referenceUrl?: string
    attribution: string
    maxZoom: number
  }
> = {
  dark: {
    name: 'Oscuro',
    icon: Moon,
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}',
    referenceUrl:
      'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, HERE, Garmin, OpenStreetMap contributors',
    maxZoom: 16,
  },
  satellite: {
    name: 'Satélite',
    icon: Satellite,
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
    referenceUrl:
      'https://server.arcgisonline.com/ArcGIS/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, Maxar, Earthstar Geographics, USDA FSA, USGS, Aerogrid, IGN',
    maxZoom: 18,
  },
  topo: {
    name: 'Relieve',
    icon: Mountain,
    url: 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
    attribution: '&copy; Esri, DeLorme, NAVTEQ, TomTom, Intermap, iPC',
    maxZoom: 18,
  },
}

function popupHtml(point: Detection): string {
  const confidence = CONFIDENCE_LABELS[point.confidence_level] ?? point.confidence_level
  const sensorColor = SENSOR_COLORS[point.sensor] ?? '#FF5C16'
  const frpVal = point.frp ?? 0
  const frpIntensity =
    frpVal > 100 ? 'Muy Alta' : frpVal > 40 ? 'Alta' : frpVal > 15 ? 'Moderada' : 'Baja'
  const frpColor =
    frpVal > 100 ? '#FF4D5E' : frpVal > 40 ? '#FF7A2F' : frpVal > 15 ? '#FFB020' : '#8EA3BE'

  return `
    <div style="min-width:240px;padding:2px">
      <!-- Encabezado con Sensor y Fecha -->
      <div style="display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #1D3048;padding-bottom:8px;margin-bottom:8px">
        <div style="display:flex;align-items:center;gap:6px">
          <span style="width:10px;height:10px;border-radius:50%;background:${sensorColor};box-shadow:0 0 8px ${sensorColor};display:inline-block"></span>
          <strong style="font-size:13px;color:#FFFFFF;letter-spacing:-0.01em">Sensor ${escapeHtml(point.sensor)}</strong>
        </div>
        <span style="font-size:10px;background:#152336;border:1px solid #1D3048;color:#BAC7D5;padding:2px 6px;border-radius:6px;font-weight:600">
          ${escapeHtml(point.satellite)}
        </span>
      </div>

      <!-- Tarjeta de Potencia Radiativa (FRP) -->
      <div style="background:rgba(13,22,34,0.7);border:1px solid #1D3048;border-radius:8px;padding:6px 8px;margin-bottom:8px;display:flex;align-items:center;justify-content:space-between">
        <div>
          <div style="font-size:9px;text-transform:uppercase;letter-spacing:0.12em;color:#8EA3BE">Potencia Radiativa (FRP)</div>
          <div style="font-size:14px;font-weight:700;color:${frpColor};font-family:monospace">
            ${point.frp !== null ? `${formatDecimal(point.frp)} MW` : 'No calibrado'}
          </div>
        </div>
        <div style="text-align:right">
          <span style="font-size:10px;font-weight:700;color:${frpColor};background:${frpColor}22;border:1px solid ${frpColor}44;padding:2px 6px;border-radius:4px">
            ${frpIntensity}
          </span>
        </div>
      </div>

      <!-- Tabla de Datos Geográficos y Temporales -->
      <table style="width:100%;border-collapse:collapse;font-size:11px;line-height:1.6">
        <tr>
          <td style="color:#8EA3BE;padding:2px 0">Ubicación:</td>
          <td style="color:#FFFFFF;text-align:right;font-weight:600">${escapeHtml(point.province)} (${escapeHtml(point.region)})</td>
        </tr>
        <tr>
          <td style="color:#8EA3BE;padding:2px 0">Fecha y hora local:</td>
          <td style="color:#FFFFFF;text-align:right">${escapeHtml(point.acq_date_local)} ${escapeHtml(point.acq_time_local)}</td>
        </tr>
        <tr>
          <td style="color:#8EA3BE;padding:2px 0">Confianza:</td>
          <td style="color:#FFFFFF;text-align:right;font-weight:600">
            ${escapeHtml(confidence)}${point.confidence_score !== null ? ` (${point.confidence_score}%)` : ''}
          </td>
        </tr>
        <tr>
          <td style="color:#8EA3BE;padding:2px 0">Coordenadas:</td>
          <td style="color:#BAC7D5;text-align:right;font-family:monospace;font-size:10px">
            ${point.latitude.toFixed(4)}°, ${point.longitude.toFixed(4)}°
          </td>
        </tr>
        <tr>
          <td style="color:#8EA3BE;padding:2px 0">Resolución píxel:</td>
          <td style="color:#BAC7D5;text-align:right;font-size:10px">
            ${point.scan ?? '—'} × ${point.track ?? '—'} km
          </td>
        </tr>
      </table>

      <!-- Nota de responsabilidad -->
      <div style="margin-top:8px;padding-top:6px;border-top:1px solid #1D3048;font-size:9.5px;color:#8EA3BE;line-height:1.4">
        ⚠️ Detección satelital de anomalía térmica; no equivale a superficie quemada ni incendio confirmado.
      </div>
    </div>
  `
}

function ClusterLayer({ points }: { points: Detection[] }) {
  const map = useMap()

  useEffect(() => {
    const group = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 46,
      disableClusteringAtZoom: 11,
      showCoverageOnHover: false,
      spiderfyOnMaxZoom: true,
    })

    points.forEach((point) => {
      if (!Number.isFinite(point.latitude) || !Number.isFinite(point.longitude)) return
      const color = SENSOR_COLORS[point.sensor]
      const marker = L.marker([point.latitude, point.longitude], {
        icon: L.divIcon({
          className: 'fire-marker-wrap',
          html: `<span class="fire-marker" style="--c:${color}"></span>`,
          iconSize: [14, 14],
          iconAnchor: [7, 7],
        }),
        keyboard: false,
      })
      marker.bindPopup(popupHtml(point), { maxWidth: 320, autoPanPadding: [30, 30] })
      marker.bindTooltip(
        `<strong>${point.sensor}</strong> · ${point.acq_date_local} ${point.acq_time_local} · ${point.frp ? `${formatDecimal(point.frp)} MW` : ''}`,
        { direction: 'top', offset: [0, -6], opacity: 0.95 },
      )
      group.addLayer(marker)
    })

    map.addLayer(group)
    return () => {
      map.removeLayer(group)
    }
  }, [map, points])

  return null
}

export interface EventFocus {
  coordinates: [number, number]
  name: string
  demo: boolean
}

function FocusEvent({ focus }: { focus: EventFocus }) {
  const map = useMap()
  const [lat, lon] = focus.coordinates
  useEffect(() => {
    map.invalidateSize()
    map.flyTo([lat, lon], 12, { duration: 0.8 })
  }, [map, lat, lon])
  return <CircleMarker center={focus.coordinates} radius={12} pathOptions={{ color: '#FFB020', weight: 3, fillOpacity: 0.25 }}>
    <Popup><strong>{focus.name}</strong><p>{focus.demo ? 'Ubicación de demostración; no representa una alerta real.' : 'Centro del evento seleccionado en Incendios.'}</p></Popup>
  </CircleMarker>
}

function FitBounds({ bbox }: { bbox: [number, number, number, number] | null }) {
  const map = useMap()
  useEffect(() => {
    map.invalidateSize()
    if (!bbox) return
    const [west, south, east, north] = bbox
    map.fitBounds(
      [
        [south, west],
        [north, east],
      ],
      { padding: [24, 24], maxZoom: 8, animate: true },
    )
  }, [bbox, map])
  return null
}

function MapControls({
  onResetZoom,
  basemap,
  onBasemapChange,
}: {
  onResetZoom: () => void
  basemap: BasemapMode
  onBasemapChange: (mode: BasemapMode) => void
}) {
  return (
    <>
      {/* Selector de Capas / Basemap (Esquina Superior Derecha) */}
      <div className="absolute right-3 top-3 z-[700] flex max-w-[calc(100%-1.5rem)] items-center gap-1 overflow-x-auto rounded-xl border border-ink-700/80 bg-ink-900/95 p-1 shadow-2xl backdrop-blur-md">
        {(Object.keys(BASEMAPS) as BasemapMode[]).map((key) => {
          const active = basemap === key
          const item = BASEMAPS[key]
          const Icon = item.icon
          return (
            <button
              key={key}
              type="button"
              onClick={() => onBasemapChange(key)}
              className={`focus-ring flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-semibold transition ${
                active
                  ? 'bg-ember-500 text-slate-950 shadow-sm'
                  : 'text-slateish hover:bg-ink-800 hover:text-white'
              }`}
              title={`Vista de mapa: ${item.name} (Sin marcas de agua)`}
            >
              <Icon size={13} className={active ? 'text-slate-950' : 'text-slate-300'} />
              <span className="hidden sm:inline">{item.name}</span>
            </button>
          )
        })}

        {/* Botón para recentrar en Ecuador */}
        <div className="mx-0.5 h-4 w-px bg-ink-700" />
        <button
          type="button"
          onClick={onResetZoom}
          className="focus-ring flex items-center gap-1 rounded-lg px-2 py-1.5 text-xs font-medium text-slateish transition hover:bg-ink-800 hover:text-white"
          title="Recentrar mapa en Ecuador"
        >
          <Maximize2 size={13} />
          <span className="hidden md:inline">Encuadrar</span>
        </button>
      </div>
    </>
  )
}

const RISK_COLORS: Record<string, string> = { Bajo: '#3DDC97', Medio: '#FACC15', Alto: '#FF8A34', Extremo: '#FF4D5E' }

function layerPopup(feature: Feature, layer: L.Layer) {
  const props = feature.properties ?? {}
  if (props.risk_level) {
    const probability = typeof props.probability === 'number' ? `${(props.probability * 100).toFixed(2)}%` : '—'
    layer.bindPopup(`<div><strong>Riesgo ${escapeHtml(String(props.risk_level))}</strong><br/>Probabilidad: ${probability}<br/>Horizonte: ${escapeHtml(String(props.window_days))} días<br/><small>Celda ~11 km; no confirma un incendio.</small></div>`)
  } else if (props.name) {
    layer.bindPopup(`<div><strong>${escapeHtml(String(props.name))}</strong><br/>${escapeHtml(String(props.category ?? 'Área protegida SNAP'))}<br/><small>Capa ambiental de referencia.</small></div>`)
  }
}

function LayerControls({ layers, onChange, horizon, onHorizonChange, alerts, alertsLoading }: {
  layers: MapLayers
  onChange: (key: keyof MapLayers, value: boolean) => void
  horizon: number
  onHorizonChange: (value: number) => void
  alerts: number
  alertsLoading: boolean
}) {
  const rows: Array<[keyof MapLayers, string, string]> = [
    ['detections', 'Focos de calor', '#FF7A2F'],
    ['risk', 'Riesgo predictivo', '#FF4D5E'],
    ['protectedAreas', 'Zonas protegidas SNAP', '#3DDC97'],
    ['alerts', `Alertas ambientales (${alertsLoading ? 'cargando…' : alerts})`, '#FF4D5E'],
  ]
  return <div className="absolute bottom-3 left-3 z-[500] w-56 rounded-xl border border-ink-700/80 bg-ink-900/95 p-3 text-xs shadow-xl backdrop-blur-md">
    <p className="mb-2 font-bold uppercase tracking-[0.12em] text-slate-300">Capas y alertas</p>
    <div className="space-y-2">{rows.map(([key, label, color]) => <label key={key} className="flex cursor-pointer items-center gap-2 text-slate-200">
      <input type="checkbox" className="accent-ember-500" checked={layers[key]} onChange={(event) => onChange(key, event.target.checked)} />
      <span className="h-2.5 w-2.5 rounded-sm" style={{ backgroundColor: color }} />{label}
    </label>)}</div>
    <label className="mt-3 block border-t border-ink-700 pt-2 text-slateish">Horizonte
      <select aria-label="Horizonte de riesgo" value={horizon} onChange={(event) => onHorizonChange(Number(event.target.value))} className="mt-1 w-full rounded border border-ink-700 bg-ink-800 px-2 py-1.5 text-xs text-white">
        <option value={0}>Hoy</option><option value={1}>1 día</option><option value={3}>3 días</option><option value={7}>7 días</option>
      </select>
    </label>
    <p className="mt-2 text-[10px] leading-snug text-slateish">Las alertas son efímeras y se recalculan con la capa publicada.</p>
  </div>
}

export function FiresMap({
  points,
  bbox,
  geojson,
  loading = false,
  total = 0,
  focus = null,
  riskGeojson = null,
  protectedAreasGeojson = null,
  alerts = [],
  layers = { detections: true, risk: true, protectedAreas: true, alerts: true },
  onLayerChange,
  riskHorizon = 7,
  onRiskHorizonChange,
  alertsLoading = false,
}: {
  points: Detection[]
  bbox: [number, number, number, number] | null
  geojson: FeatureCollection | null
  loading?: boolean
  total?: number
  focus?: EventFocus | null
  riskGeojson?: FeatureCollection | null
  protectedAreasGeojson?: FeatureCollection | null
  alerts?: EnvironmentalAlert[]
  layers?: MapLayers
  onLayerChange?: (key: keyof MapLayers, value: boolean) => void
  riskHorizon?: number
  onRiskHorizonChange?: (value: number) => void
  alertsLoading?: boolean
}) {
  const [basemap, setBasemap] = useState<BasemapMode>(() =>
    document.documentElement.dataset.theme === 'light' ? 'topo' : 'dark',
  )
  const [resetNonce, setResetNonce] = useState(0)

  // El fondo cartográfico acompaña al tema general. Los controles mantienen
  // contraste alto para no perder legibilidad sobre imágenes o relieve.
  useEffect(() => {
    const root = document.documentElement
    const syncBasemapWithTheme = () => setBasemap(root.dataset.theme === 'light' ? 'topo' : 'dark')
    syncBasemapWithTheme()
    const observer = new MutationObserver(syncBasemapWithTheme)
    observer.observe(root, { attributes: true, attributeFilter: ['data-theme'] })
    return () => observer.disconnect()
  }, [])

  const modisCount = points.filter((point) => point.sensor === 'MODIS').length
  const viirsCount = points.filter((point) => point.sensor === 'VIIRS').length

  const handleResetZoom = () => {
    setResetNonce((v) => v + 1)
  }

  const currentBasemap = BASEMAPS[basemap]

  return (
    <div className="map-surface relative h-[66vh] min-h-[500px] w-full min-w-0 max-w-full overflow-hidden rounded-2xl border border-ink-700/80 shadow-2xl">
      <MapContainer
        center={[-1.6, -78.4]}
        zoom={6}
        minZoom={5}
        maxZoom={18}
        zoomControl={false}
        className="h-full w-full"
        preferCanvas
      >
        {/* Capa Base de Mapa Esri (Sin marcas de agua de Carto) */}
        <TileLayer
          key={basemap}
          attribution={currentBasemap.attribution}
          url={currentBasemap.url}
          maxZoom={currentBasemap.maxZoom}
        />

        {/* Capa de Referencia (Límites y Ciudades) si aplica */}
        {currentBasemap.referenceUrl && (
          <TileLayer
            key={`${basemap}-labels`}
            url={currentBasemap.referenceUrl}
            maxZoom={currentBasemap.maxZoom}
            opacity={0.8}
          />
        )}

        {/* Delimitación Provincial GeoJSON */}
        {geojson && (
          <GeoJSON
            data={geojson}
            interactive={false}
            style={{
              color: '#FF7A2F',
              weight: 0.9,
              opacity: 0.45,
              fillColor: '#FF5C16',
              fillOpacity: 0.02,
              dashArray: '3 4',
            }}
          />
        )}

        {layers.risk && riskGeojson && <GeoJSON data={riskGeojson} onEachFeature={layerPopup} style={(feature) => {
          const color = RISK_COLORS[String(feature?.properties?.risk_level)] ?? '#8EA3BE'
          return { color, weight: 0.4, opacity: 0.65, fillColor: color, fillOpacity: 0.30 }
        }} />}
        {layers.protectedAreas && protectedAreasGeojson && <GeoJSON data={protectedAreasGeojson} onEachFeature={layerPopup} style={{ color: '#3DDC97', weight: 1.6, opacity: 0.9, fillColor: '#3DDC97', fillOpacity: 0.10 }} />}
        {layers.detections && <ClusterLayer points={points} />}
        {layers.alerts && alerts.map((alert) => <CircleMarker key={alert.id} center={alert.coordinates} radius={alert.priority === 'critical' ? 10 : 8} pathOptions={{ color: '#fff', weight: 2, fillColor: '#FF4D5E', fillOpacity: 0.95 }}>
          <Popup><strong>{alert.title}</strong><p>{alert.protected_area.name} · {alert.protected_area.category}</p>{alert.risk && <p>Riesgo {alert.risk.level}: {(alert.risk.probability * 100).toFixed(2)}% · {alert.risk.window_days} días</p>}<small>{alert.disclaimer}</small></Popup>
        </CircleMarker>)}
        {focus ? (
          <FocusEvent key={`focus-${resetNonce}`} focus={focus} />
        ) : (
          <FitBounds key={`bounds-${resetNonce}`} bbox={bbox} />
        )}
        <ZoomControl position="bottomright" />
        <ScaleControl position="bottomleft" imperial={false} />
      </MapContainer>

      {/* Controles del Mapa: Basemap Switcher y Re-centrar */}
      <MapControls
        basemap={basemap}
        onBasemapChange={setBasemap}
        onResetZoom={handleResetZoom}
      />
      {onLayerChange && onRiskHorizonChange && <LayerControls layers={layers} onChange={onLayerChange} horizon={riskHorizon} onHorizonChange={onRiskHorizonChange} alerts={alerts.length} alertsLoading={alertsLoading} />}

      {/* Leyenda Inteligente de Sensores (Esquina Superior Izquierda) */}
      <div className="pointer-events-none absolute left-3 top-3 z-[500] rounded-xl border border-ink-700/80 bg-ink-900/95 p-3 shadow-xl backdrop-blur-md">
        <div className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-300">
          <Flame size={12} className="text-ember-400" />
          <span>Focos Detectados</span>
        </div>

        <div className="mt-2 space-y-1.5 text-xs">
          <div className="flex items-center justify-between gap-3 text-slate-200">
            <span className="flex items-center gap-1.5 font-medium">
              <span
                className="h-2.5 w-2.5 rounded-full ring-2 ring-white/10"
                style={{ background: SENSOR_COLORS.MODIS }}
              />
              MODIS (~1 km)
            </span>
            <span className="num font-bold text-white">{formatNumber(modisCount)}</span>
          </div>

          <div className="flex items-center justify-between gap-3 text-slate-200">
            <span className="flex items-center gap-1.5 font-medium">
              <span
                className="h-2.5 w-2.5 rounded-full ring-2 ring-white/10"
                style={{ background: SENSOR_COLORS.VIIRS }}
              />
              VIIRS (~375 m)
            </span>
            <span className="num font-bold text-white">{formatNumber(viirsCount)}</span>
          </div>
        </div>

        <div className="mt-2.5 border-t border-ink-800 pt-1.5 text-[10px] text-slateish">
          <span>Pasa el cursor o haz clic para ver FRP y hora</span>
        </div>
      </div>

      {/* Alerta de Límite de Puntos */}
      {total > points.length && (
        <div className="absolute bottom-3 left-3 z-[500] max-w-sm rounded-xl border border-amber-400/40 bg-ink-900/95 px-3 py-2 text-xs leading-relaxed text-amber-100 shadow-xl backdrop-blur-md">
          <span className="font-bold text-amber-300">Vista optimizada:</span> Mostrando{' '}
          <strong>{formatNumber(points.length)}</strong> de <strong>{formatNumber(total)}</strong> focos.
          Filtra por provincia o un período menor para ver cada punto individual.
        </div>
      )}

      {/* Loader */}
      {loading && (
        <div className="absolute inset-0 z-[600] flex items-center justify-center bg-ink-950/70 backdrop-blur-sm">
          <div className="flex items-center gap-2.5 rounded-xl border border-ink-700 bg-ink-900 px-5 py-3 text-xs font-semibold text-white shadow-2xl">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-ember-400 border-t-transparent" />
            Cargando detecciones orbitales de Ecuador…
          </div>
        </div>
      )}
    </div>
  )
}
