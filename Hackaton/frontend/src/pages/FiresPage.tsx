import {
  AlertTriangle,
  CheckCircle2,
  Compass,
  ExternalLink,
  Flame,
  MapPin,
  Moon,
  Radio,
  ShieldAlert,
  TreePine,
  Wind,
} from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/layout/Layout'
import { FiltersBar } from '../components/layout/FiltersBar'
import {
  Badge,
  Card,
  Notice,
  SectionHeading,
  StatCard,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { formatDecimal, formatNumber } from '../lib/format'

interface FireCluster {
  id: string
  name: string
  province: string
  canton: string
  frpTotal: number
  pointsCount: number
  severity: 'critical' | 'moderate' | 'minor'
  isNight: boolean
  inProtectedArea: boolean
  protectedAreaName?: string
  lastDetected: string
  coordinates: [number, number]
}

// Datos representativos calibrados con eventos históricos y listos para conectar con /api/v1/fire-events
const MOCK_CLUSTERS: FireCluster[] = [
  {
    id: 'FC-EC-01',
    name: 'Quilanga - San Antonio',
    province: 'Loja',
    canton: 'Quilanga',
    frpTotal: 184.5,
    pointsCount: 38,
    severity: 'critical',
    isNight: true,
    inProtectedArea: false,
    lastDetected: 'Paso nocturno (02:15 hora local)',
    coordinates: [-4.298, -79.405],
  },
  {
    id: 'FC-EC-02',
    name: 'Sigchos - Chugchillán',
    province: 'Cotopaxi',
    canton: 'Sigchos',
    frpTotal: 96.2,
    pointsCount: 19,
    severity: 'critical',
    isNight: false,
    inProtectedArea: true,
    protectedAreaName: 'Zona amortiguamiento Ilinizas',
    lastDetected: 'Paso diurno (13:40 hora local)',
    coordinates: [-0.685, -78.892],
  },
  {
    id: 'FC-EC-03',
    name: 'Nanegalito - Calacalí',
    province: 'Pichincha',
    canton: 'Quito',
    frpTotal: 42.1,
    pointsCount: 9,
    severity: 'moderate',
    isNight: false,
    inProtectedArea: true,
    protectedAreaName: 'Reserva Geobotánica Pululahua',
    lastDetected: 'Paso diurno (14:05 hora local)',
    coordinates: [0.012, -78.531],
  },
  {
    id: 'FC-EC-04',
    name: 'Paquisha - Cordillera',
    province: 'Zamora Chinchipe',
    canton: 'Paquisha',
    frpTotal: 22.4,
    pointsCount: 4,
    severity: 'minor',
    isNight: false,
    inProtectedArea: false,
    lastDetected: 'Paso diurno (11:20 hora local)',
    coordinates: [-3.931, -78.672],
  },
]

export default function FiresPage() {
  const { regionName } = useFilters()
  const [activeTab, setActiveTab] = useState<'clusters' | 'risk' | 'filters'>('clusters')

  const criticalCount = MOCK_CLUSTERS.filter((c) => c.severity === 'critical').length
  const nightCount = MOCK_CLUSTERS.filter((c) => c.isNight).length
  const totalFRP = MOCK_CLUSTERS.reduce((sum, c) => sum + c.frpTotal, 0)

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Módulo Especializado"
        title={`Incendios Forestales & Alertas Críticas · ${regionName}`}
        description="Identificación de incendios reales mediante clustering espaciotemporal (DBSCAN), descarte de falsos positivos térmicos industriales y evaluación de susceptibilidad por cantón."
        icon={ShieldAlert}
        actions={
          <Link
            to="/mapa"
            className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60 hover:bg-ember-500/15"
          >
            <Compass size={14} /> Ver en Mapa General
          </Link>
        }
      />

      <FiltersBar />

      <div className="relative z-10 mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Incendios agrupados"
          value={formatNumber(MOCK_CLUSTERS.length)}
          sub="Clusters espaciales confirmados"
          icon={Flame}
        />
        <StatCard
          label="Alertas críticas"
          value={formatNumber(criticalCount)}
          sub="FRP > 100 MW o propagación nocturna"
          icon={AlertTriangle}
          accent="#FF4D5E"
        />
        <StatCard
          label="Actividad nocturna"
          value={formatNumber(nightCount)}
          sub="Fuego activo fuera de control"
          icon={Moon}
          accent="#FFB020"
        />
        <StatCard
          label="Potencia térmica total"
          value={`${formatDecimal(totalFRP, 0)} MW`}
          sub="Suma de FRP en eventos agrupados"
          icon={Radio}
          accent="#3DDC97"
        />
      </div>

      {/* Selector de Pestañas del Módulo */}
      <div className="mb-4 flex flex-wrap items-center gap-2 border-b border-ink-700/60 pb-3">
        <button
          type="button"
          onClick={() => setActiveTab('clusters')}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
            activeTab === 'clusters'
              ? 'bg-ember-500/20 text-ember-300 border border-ember-400/30'
              : 'text-slateish hover:bg-ink-800 hover:text-white'
          }`}
        >
          Eventos Agrupados (Clusters)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('risk')}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
            activeTab === 'risk'
              ? 'bg-ember-500/20 text-ember-300 border border-ember-400/30'
              : 'text-slateish hover:bg-ink-800 hover:text-white'
          }`}
        >
          Modelo de Susceptibilidad (ML)
        </button>
        <button
          type="button"
          onClick={() => setActiveTab('filters')}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
            activeTab === 'filters'
              ? 'bg-ember-500/20 text-ember-300 border border-ember-400/30'
              : 'text-slateish hover:bg-ink-800 hover:text-white'
          }`}
        >
          Filtros Contextuales & Falsos Positivos
        </button>
      </div>

      {activeTab === 'clusters' && (
        <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
          <div className="space-y-3">
            {MOCK_CLUSTERS.map((cluster) => (
              <Card key={cluster.id} className="relative overflow-hidden">
                <div
                  className="absolute left-0 top-0 bottom-0 w-1"
                  style={{
                    background:
                      cluster.severity === 'critical'
                        ? '#FF4D5E'
                        : cluster.severity === 'moderate'
                          ? '#FFB020'
                          : '#3DDC97',
                  }}
                />
                <div className="pl-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-white sm:text-sm">{cluster.name}</span>
                      <Badge
                        tone={
                          cluster.severity === 'critical'
                            ? 'critical'
                            : cluster.severity === 'moderate'
                              ? 'warning'
                              : 'positive'
                        }
                      >
                        {cluster.severity === 'critical'
                          ? 'Alerta Crítica'
                          : cluster.severity === 'moderate'
                            ? 'Moderado'
                            : 'Quema Menor'}
                      </Badge>
                      {cluster.isNight && (
                        <Badge tone="critical" className="flex items-center gap-1">
                          <Moon size={10} /> Detección Nocturna
                        </Badge>
                      )}
                    </div>
                    <span className="text-[10px] text-slateish">{cluster.lastDetected}</span>
                  </div>

                  <p className="mt-1 flex items-center gap-1 text-xs text-slateish">
                    <MapPin size={12} className="text-ember-400" />
                    {cluster.canton}, {cluster.province} · {cluster.pointsCount} focos agrupados
                  </p>

                  {cluster.inProtectedArea && (
                    <div className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-1 text-[11px] text-emerald-300">
                      <TreePine size={12} />
                      Área protegida / amortiguamiento: {cluster.protectedAreaName}
                    </div>
                  )}

                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-ink-700/60 pt-2 text-xs">
                    <span className="text-slateish">
                      Potencia acumulada:{' '}
                      <strong className="text-white">{formatDecimal(cluster.frpTotal, 1)} MW</strong>
                    </span>
                    <Link
                      to="/mapa"
                      className="inline-flex items-center gap-1 text-[11px] font-semibold text-ember-300 transition hover:text-ember-200"
                    >
                      Inspeccionar coordenadas en mapa <ExternalLink size={11} />
                    </Link>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          <div className="space-y-4">
            <Card>
              <SectionHeading
                eyebrow="Criterio Científico"
                title="¿Cómo se identifica un incendio real?"
                description="Algoritmo de clustering espacial DBSCAN con radio de 1.5 a 2 km y ventana temporal de 24h."
              />
              <ul className="space-y-2.5 text-xs leading-relaxed text-slateish">
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-mint" />
                  <span>
                    <strong className="text-white">Agrupamiento de píxeles:</strong> Se agrupan múltiples detecciones de MODIS (1 km) y VIIRS (375 m) en un solo polígono envolvente.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-mint" />
                  <span>
                    <strong className="text-white">Potencia Radiativa (FRP):</strong> Valores mayores a 100 MW indican frentes de fuego extensos con alta biomasa en combustión.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <CheckCircle2 size={14} className="mt-0.5 shrink-0 text-mint" />
                  <span>
                    <strong className="text-white">Paso nocturno (daynight == &apos;N&apos;):</strong> Es una señal crítica; las quemas agrícolas no se realizan de noche. Si el sensor detecta calor a las 02:00, el fuego está fuera de control.
                  </span>
                </li>
              </ul>
            </Card>

            <Notice tone="warning" title="Respuesta y Emergencias">
              Ante incendios forestales activos en áreas de cobertura vegetal o páramo, la notificación formal debe canalizarse con el <strong>ECU 911</strong> y los Cuerpos de Bomberos cantonales.
            </Notice>
          </div>
        </div>
      )}

      {activeTab === 'risk' && (
        <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
          <Card>
            <SectionHeading
              eyebrow="Modelo Predictivo"
              title="Semáforo de Susceptibilidad Cantonal"
              description="Modelo supervisado entrenado con histórico 2022-2026, clima, topografía y combustible vegetal."
            />
            <div className="space-y-2.5">
              {[
                { canton: 'Quilanga (Loja)', risk: 'Extremo', score: 0.92, factor: 'Sequía prolongada + vientos > 35 km/h' },
                { canton: 'Sigchos (Cotopaxi)', risk: 'Alto', score: 0.78, factor: 'Pendientes fuertes + vegetación seca' },
                { canton: 'Pimampiro (Imbabura)', risk: 'Alto', score: 0.74, factor: 'Baja humedad relativa (< 25%)' },
                { canton: 'Mejía (Pichincha)', risk: 'Medio', score: 0.52, factor: 'Zonas de páramo con actividad agrícola' },
                { canton: 'Santa Cruz (Galápagos)', risk: 'Bajo', score: 0.15, factor: 'Humedad costera alta' },
              ].map((item) => (
                <div
                  key={item.canton}
                  className="flex items-center justify-between rounded-lg border border-ink-700/60 bg-ink-800/40 p-3 text-xs"
                >
                  <div>
                    <p className="font-semibold text-white">{item.canton}</p>
                    <p className="text-[11px] text-slateish">{item.factor}</p>
                  </div>
                  <div className="text-right">
                    <Badge
                      tone={
                        item.risk === 'Extremo'
                          ? 'critical'
                          : item.risk === 'Alto'
                            ? 'critical'
                            : item.risk === 'Medio'
                              ? 'warning'
                              : 'positive'
                      }
                    >
                      Riesgo {item.risk} ({Math.round(item.score * 100)}%)
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card>
            <SectionHeading
              eyebrow="Variables del Modelo"
              title="Factores que Alimentan la Predicción"
              description="Enfoque preventivo para anticipar focos antes de que comience la ignición."
            />
            <div className="space-y-3 text-xs text-slateish">
              <div className="rounded-lg border border-ink-700/60 bg-ink-800/30 p-2.5">
                <p className="flex items-center gap-1.5 font-semibold text-white">
                  <Wind size={13} className="text-sky-300" /> Meteorología en tiempo real
                </p>
                <p className="mt-1 text-[11px]">
                  Temperatura máxima diurna, velocidad de rachas de viento y días consecutivos sin precipitación (Open-Meteo / ERA5).
                </p>
              </div>
              <div className="rounded-lg border border-ink-700/60 bg-ink-800/30 p-2.5">
                <p className="flex items-center gap-1.5 font-semibold text-white">
                  <TreePine size={13} className="text-emerald-300" /> Cobertura vegetal (NDVI)
                </p>
                <p className="mt-1 text-[11px]">
                  Contenido de humedad y estrés hídrico de la biomasa en páramos y bosques andinos.
                </p>
              </div>
              <div className="rounded-lg border border-ink-700/60 bg-ink-800/30 p-2.5">
                <p className="flex items-center gap-1.5 font-semibold text-white">
                  <Compass size={13} className="text-amber-300" /> Topografía y factor humano
                </p>
                <p className="mt-1 text-[11px]">
                  Pendiente del terreno (DEM) y proximidad a vías o asentamientos donde se realizan quemas agropecuarias.
                </p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'filters' && (
        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <SectionHeading
              eyebrow="Descarte de Ruido"
              title="Filtro de Mecheros Petroleros (Falsos Positivos)"
              description="La Amazonía ecuatoriana presenta anomalías térmicas continuas por quema de gas en campos petroleros."
            />
            <p className="text-xs leading-relaxed text-slateish">
              En provincias como <strong>Orellana</strong> y <strong>Sucumbíos</strong>, los satélites MODIS y VIIRS detectan constantemente altas temperaturas que no son incendios forestales, sino mecheros de combustión de gas en pozos de extracción.
            </p>
            <div className="mt-3 rounded-lg border border-ink-700/70 bg-ink-850 p-3 text-xs">
              <p className="font-semibold text-white">Máscara de Coordenadas Fijas:</p>
              <p className="mt-1 text-slateish">
                El sistema cruza cada detección con el catálogo georreferenciado de mecheros industriales y los etiqueta automáticamente para evitar falsas alarmas ciudadanas.
              </p>
            </div>
          </Card>

          <Card>
            <SectionHeading
              eyebrow="Prioridad Ecológica"
              title="Cruce con el Sistema Nacional de Áreas Protegidas (SNAP)"
              description="Evaluación de impacto inmediato en reservas biológicas y parques nacionales."
            />
            <p className="text-xs leading-relaxed text-slateish">
              Un foco de calor que coincide geográficamente con un parque nacional o reserva ecológica (ej. Cayambe-Coca, Cotopaxi, Podocarpus) eleva automáticamente su severidad a <span className="font-semibold text-red-400">Prioridad Máxima</span> en el centro de mando.
            </p>
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/10 p-3 text-xs text-emerald-200">
              <TreePine size={16} className="shrink-0" />
              <span>Capas SNAP integradas con geometrías vectoriales del Ministerio de Ambiente, Agua y Transición Ecológica (MAATE).</span>
            </div>
          </Card>
        </div>
      )}
    </div>
  )
}

