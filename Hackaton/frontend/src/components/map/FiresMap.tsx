import L from 'leaflet'
import 'leaflet.markercluster'
import { useEffect } from 'react'
import type { FeatureCollection } from 'geojson'
import { GeoJSON, MapContainer, ScaleControl, TileLayer, ZoomControl, useMap } from 'react-leaflet'
import type { Detection } from '../../types/api'
import { CONFIDENCE_LABELS, SENSOR_COLORS } from '../../lib/constants'
import { escapeHtml, formatDecimal, formatNumber } from '../../lib/format'

function popupHtml(point: Detection): string {
  const confidence = CONFIDENCE_LABELS[point.confidence_level] ?? point.confidence_level
  const rows = [
    ['Fecha local', `${point.acq_date_local} ${point.acq_time_local}`],
    ['Sensor', `${point.sensor} · ${point.satellite}`],
    ['Confianza', `${confidence}${point.confidence_score !== null ? ` (${point.confidence_score})` : ''}`],
    ['FRP', point.frp !== null ? `${formatDecimal(point.frp)} MW` : '—'],
    ['Provincia', point.province],
    ['Región', point.region],
    ['Producto', point.source_product],
    ['Coordenadas', `${point.latitude.toFixed(4)}, ${point.longitude.toFixed(4)}`],
    ['Píxel scan/track', `${point.scan ?? '—'} / ${point.track ?? '—'} km`],
  ]
  return `
    <div style="min-width:220px">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:8px">
        <span style="width:8px;height:8px;border-radius:99px;background:${SENSOR_COLORS[point.sensor]};display:inline-block"></span>
        <strong style="font-size:12px">Detección ${escapeHtml(point.sensor)}</strong>
      </div>
      <table style="width:100%;border-collapse:collapse;font-size:11px">
        ${rows
          .map(
            ([label, value]) =>
              `<tr><td style="color:#8EA3BE;padding:2px 8px 2px 0;white-space:nowrap">${escapeHtml(label)}</td><td style="color:#E8EFF9;text-align:right">${escapeHtml(value)}</td></tr>`,
          )
          .join('')}
      </table>
      <p style="margin:8px 0 0;color:#8EA3BE;font-size:10px;line-height:1.4">
        Detección de foco de calor; no es un incendio confirmado ni superficie quemada.
      </p>
      <p style="margin:4px 0 0;color:#5E7490;font-size:9px">ID ${escapeHtml(point.id)}</p>
    </div>
  `
}

function ClusterLayer({ points }: { points: Detection[] }) {
  const map = useMap()

  useEffect(() => {
    const group = L.markerClusterGroup({
      chunkedLoading: true,
      maxClusterRadius: 48,
      disableClusteringAtZoom: 10,
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
        `${point.sensor} · ${point.acq_date_local} · ${CONFIDENCE_LABELS[point.confidence_level] ?? point.confidence_level}`,
        { direction: 'top', offset: [0, -6], opacity: 0.9 },
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

export function FiresMap({
  points,
  bbox,
  geojson,
  loading = false,
  total = 0,
}: {
  points: Detection[]
  bbox: [number, number, number, number] | null
  geojson: FeatureCollection | null
  loading?: boolean
  total?: number
}) {
  const modisCount = points.filter((point) => point.sensor === 'MODIS').length
  const viirsCount = points.filter((point) => point.sensor === 'VIIRS').length

  return (
    <div className="relative h-[62vh] min-h-[460px] overflow-hidden rounded-2xl border border-ink-700/80">
      <MapContainer
        center={[-1.6, -78.4]}
        zoom={6}
        minZoom={5}
        maxZoom={17}
        zoomControl={false}
        className="h-full w-full"
        preferCanvas
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>'
          url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
          subdomains="abcd"
          maxZoom={19}
        />
        {geojson && (
          <GeoJSON
            data={geojson}
            interactive={false}
            style={{
              color: '#FF7A2F',
              weight: 0.8,
              opacity: 0.35,
              fillColor: '#FF5C16',
              fillOpacity: 0.015,
              dashArray: '4 4',
            }}
          />
        )}
        <ClusterLayer points={points} />
        <FitBounds bbox={bbox} />
        <ZoomControl position="bottomright" />
        <ScaleControl position="bottomleft" imperial={false} />
      </MapContainer>

      <div className="pointer-events-none absolute left-3 top-3 z-[500] rounded-xl border border-ink-700/80 bg-ink-900/90 px-3 py-2 backdrop-blur">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slateish">Leyenda</p>
        <div className="mt-1.5 space-y-1 text-[11px]">
          <p className="flex items-center gap-2 text-slate-100">
            <span className="h-2 w-2 rounded-full" style={{ background: SENSOR_COLORS.MODIS }} /> MODIS · ~1 km
            <span className="num ml-auto text-slateish">{formatNumber(modisCount)}</span>
          </p>
          <p className="flex items-center gap-2 text-slate-100">
            <span className="h-2 w-2 rounded-full" style={{ background: SENSOR_COLORS.VIIRS }} /> VIIRS · ~375 m
            <span className="num ml-auto text-slateish">{formatNumber(viirsCount)}</span>
          </p>
          <p className="pt-1 text-[10px] text-slateish">Agrupado por proximidad · clic para detalle</p>
        </div>
      </div>

      {total > points.length && (
        <div className="absolute bottom-3 left-3 z-[500] max-w-xs rounded-lg border border-amber-400/30 bg-amber-950/80 px-3 py-2 text-[10px] leading-relaxed text-amber-100 backdrop-blur">
          Mostrando {formatNumber(points.length)} de {formatNumber(total)} detecciones. Reduce el periodo o la región
          para ver todas en el mapa.
        </div>
      )}

      {loading && (
        <div className="absolute inset-0 z-[600] flex items-center justify-center bg-ink-950/60 backdrop-blur-sm">
          <div className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-900 px-4 py-2 text-xs text-slate-200">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-ember-400 border-t-transparent" />
            Cargando detecciones…
          </div>
        </div>
      )}
    </div>
  )
}
