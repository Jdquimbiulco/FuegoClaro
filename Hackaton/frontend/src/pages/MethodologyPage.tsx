import {
  Activity,
  BookOpen,
  Braces,
  CheckCircle2,
  ChevronDown,
  Database,
  FileJson,
  GitBranch,
  Globe2,
  Hash,
  Layers,
  MapPin,
  Satellite,
  ShieldCheck,
  Sigma,
  Terminal,
} from 'lucide-react'
import { PageHeader } from '../components/layout/Layout'
import {
  Badge,
  Card,
  ErrorState,
  LoadingBlock,
  Notice,
  SectionHeading,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { formatNumber } from '../lib/format'
import type { ProvenanceResponse } from '../types/api'

const SIMPLE_STEPS = [
  {
    title: 'Descargamos',
    detail: 'Pedimos a NASA FIRMS las detecciones del territorio ecuatoriano y las guardamos tal como llegan.',
  },
  {
    title: 'Limpiamos',
    detail: 'Quitamos coordenadas inválidas, fechas imposibles y duplicados. No inventamos ni rellenamos datos.',
  },
  {
    title: 'Ubicamos',
    detail: 'Asignamos provincia y región (Costa, Sierra, Amazonía, Galápagos) usando los límites geográficos.',
  },
  {
    title: 'Comparamos',
    detail: 'Calculamos conteos por día, región y sensor; series, calendario y diferencias entre MODIS y VIIRS.',
  },
  {
    title: 'Detectamos anomalías',
    detail: 'Comparamos cada día con la misma época de años anteriores para ver si el conteo fue inusualmente alto o bajo.',
  },
  {
    title: 'Explicamos',
    detail: 'Generamos hallazgos con plantillas fijas. No usamos IA generativa para inventar cifras ni conclusiones.',
  },
]

const READING_KEYS = [
  {
    title: 'Detección',
    detail:
      'Es una señal de calor vista por el satélite en un píxel. Puede ser fuego, pero también suelo caliente, actividad industrial o una falsa alarma.',
    icon: Activity,
  },
  {
    title: 'Conteo',
    detail:
      'Es cuántas detecciones hubo en un día, una región o un sensor. Sirve para comparar patrones; no mide hectáreas ni gravedad.',
    icon: Layers,
  },
  {
    title: 'Anomalía',
    detail:
      'Es un conteo que se aleja de lo normal para esa fecha y región. Dice “inusual”, no “peligroso” ni “causado por algo”.',
    icon: Sigma,
  },
]

const PIPELINE = [
  {
    title: 'Descarga NASA FIRMS',
    detail:
      'Area API con bbox de Ecuador, bloques de 5 días y separación explícita entre productos SP (procesamiento estándar) y NRT (tiempo casi real). La MAP_KEY vive solo en el backend.',
  },
  {
    title: 'Normalización canónica',
    detail:
      'MODIS y VIIRS se mapean a un esquema único: sensor, satélite, instrumento, producto, fecha/hora, confianza original, FRP, temperaturas de brillo, scan/track y geometría del píxel.',
  },
  {
    title: 'Filtro geográfico',
    detail:
      'Cada punto se cruza con las geometrías provinciales de Ecuador (Natural Earth 1:10m). Los puntos fuera del territorio se excluyen y se contabilizan en el manifiesto.',
  },
  {
    title: 'Provincia y región',
    detail:
      'Se asigna provincia y región natural (Costa, Sierra, Amazonía, Galápagos) por contención geométrica. No se infiere ubicación por centroides ni por cercanía.',
  },
  {
    title: 'Hora local y validación',
    detail:
      'Se calcula fecha/hora local con UTC-5 para Ecuador continental y UTC-6 para Galápagos. Se descartan coordenadas inválidas, fechas imposibles y duplicados deterministas.',
  },
  {
    title: 'Agregación y análisis',
    detail:
      'Conteos diarios por región y sensor; series, calendario, comparación, anomalías con z-score y FDR, y hallazgos deterministas. Ningún valor se rellena artificialmente.',
  },
]

const CONFIDENCE_ROWS = [
  {
    sensor: 'MODIS',
    original: '0–100 (entero)',
    mapping: 'Baja < 30 · Nominal 30–79 · Alta ≥ 80',
    note: 'El score numérico original se conserva en confidence_score.',
  },
  {
    sensor: 'VIIRS',
    original: 'l / n / h',
    mapping: 'low → Baja · nominal → Nominal · high → Alta',
    note: 'No se inventa un score numérico para VIIRS.',
  },
]

const ENDPOINTS = [
  ['GET', '/api/v1/meta', 'Metadatos, cobertura y catálogo de regiones'],
  ['GET', '/api/v1/regions/geojson', 'Geometrías provinciales para el mapa'],
  ['GET', '/api/v1/detections', 'Detecciones paginadas o GeoJSON'],
  ['GET', '/api/v1/stats/summary', 'Indicadores del periodo filtrado'],
  ['GET', '/api/v1/stats/timeseries', 'Serie diaria, semanal o mensual'],
  ['GET', '/api/v1/calendar', 'Calendario mensual por día local'],
  ['GET', '/api/v1/comparison', 'Comparación MODIS vs VIIRS'],
  ['GET', '/api/v1/anomalies', 'Anomalías con z-score y FDR'],
  ['GET', '/api/v1/insights', 'Hallazgos deterministas'],
  ['GET', '/api/v1/export/detections.csv', 'Exportación de detecciones filtradas'],
]

function bytes(value: number | undefined): string {
  if (!value) return '—'
  if (value > 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`
  return `${(value / 1024).toFixed(1)} KB`
}

export default function MethodologyPage() {
  const { meta } = useFilters()
  const provenanceState = useApi<ProvenanceResponse>('/provenance')
  const provenance = provenanceState.data
  const manifest = provenance?.manifest
  const sources = manifest?.sources ?? []

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Metodología"
        title="Cómo funciona FuegoClaro"
        description="De dónde salen los datos, qué hacemos con ellos y cuáles son sus límites. En una frase: mostramos señales de calor detectadas por satélite, no incendios confirmados."
        icon={BookOpen}
      />

      <Card className="mb-4 border-ember-400/20 bg-ember-500/[0.04]">
        <SectionHeading
          eyebrow="La idea en 30 segundos"
          title="Qué hace FuegoClaro"
          description="Tomamos datos públicos de satélite, los ordenamos y los convertimos en una lectura fácil de explorar. No creamos datos ni conclusiones que no estén en la fuente."
        />
        <div className="grid gap-2 sm:grid-cols-3">
          {[
            {
              icon: Satellite,
              title: '1. Recibimos',
              detail: 'NASA publica detecciones de calor de dos satélites. FuegoClaro las descarga para Ecuador.',
            },
            {
              icon: Layers,
              title: '2. Ordenamos',
              detail: 'Limpiamos, ubicamos cada detección en su provincia y la comparamos con el histórico.',
            },
            {
              icon: MapPin,
              title: '3. Mostramos',
              detail: 'Convertimos esos datos en mapas, conteos, comparaciones, anomalías y hallazgos.',
            },
          ].map(({ icon: Icon, title, detail }) => (
            <div key={title} className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
              <div className="flex items-center gap-2">
                <span className="rounded-lg border border-ember-400/25 bg-ember-500/10 p-1.5 text-ember-300">
                  <Icon size={14} />
                </span>
                <p className="text-xs font-semibold text-white">{title}</p>
              </div>
              <p className="mt-1.5 text-[11px] leading-relaxed text-slateish">{detail}</p>
            </div>
          ))}
        </div>
        <div className="mt-3">
          <Notice tone="warning" title="La frase más importante" icon={ShieldCheck}>
            Un punto en el mapa significa “el satélite vio una señal de calor en ese píxel”, no “hay un incendio
            confirmado”. Tampoco mide el área quemada ni la gravedad del fuego.
          </Notice>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <SectionHeading
            eyebrow="Cómo leer el tablero"
            title="Detección, conteo y anomalía no son lo mismo"
            description="Tres ideas ayudan a explicar cualquier pantalla sin tecnicismos."
          />
          <div className="space-y-2">
            {READING_KEYS.map(({ icon: Icon, title, detail }) => (
              <div key={title} className="flex gap-2 rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
                <span className="mt-0.5 rounded-lg border border-sky-400/25 bg-sky-400/10 p-1.5 text-sky-300">
                  <Icon size={14} />
                </span>
                <div>
                  <p className="text-xs font-semibold text-white">{title}</p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-slateish">{detail}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Los dos satélites"
            title="MODIS y VIIRS ven diferente"
            description="Los dos detectan calor, pero no con el mismo nivel de detalle. Por eso sus números no se leen como equivalentes."
          />
          <div className="grid gap-2 sm:grid-cols-2">
            <div className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#FFB020]" />
                <p className="text-xs font-semibold text-white">MODIS · píxel ~1 km</p>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-slateish">
                Ve áreas más grandes y suele generar menos detecciones. Su confianza es un número de 0 a 100.
              </p>
            </div>
            <div className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-[#FF4D5E]" />
                <p className="text-xs font-semibold text-white">VIIRS · píxel ~375 m</p>
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-slateish">
                Ve detalles más finos y suele generar más detecciones. Su confianza es una categoría: baja, nominal o
                alta.
              </p>
            </div>
          </div>
          <div className="mt-3">
            <Notice tone="neutral" title="No se suman como si fueran lo mismo">
              Una misma zona puede generar varios píxeles VIIRS y uno solo MODIS. Comparar sus conteos sirve para ver
              diferencias de sensibilidad, no para estimar superficie quemada.
            </Notice>
          </div>
        </Card>
      </div>

      <div className="mt-4 grid gap-4 xl:grid-cols-[1.15fr_1fr]">
        <Card>
          <SectionHeading
            eyebrow="Fuente"
            title="NASA FIRMS: datos públicos de satélite"
            description="Fire Information for Resource Management System. Usamos MODIS Collection 6.1 y VIIRS 375 m para el territorio ecuatoriano."
          />
          {provenanceState.error ? (
            <ErrorState message={provenanceState.error} onRetry={provenanceState.refetch} />
          ) : provenanceState.loading && !provenance ? (
            <LoadingBlock label="Cargando procedencia del dataset…" />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-[10px]">
                <thead>
                  <tr className="border-b border-ink-700 text-[9px] uppercase tracking-wider text-slateish">
                    <th className="py-1.5 pr-2 font-medium">Producto</th>
                    <th className="py-1.5 pr-2 font-medium">Sensor</th>
                    <th className="py-1.5 pr-2 font-medium">Cobertura solicitada</th>
                    <th className="py-1.5 text-right font-medium">Registros</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="py-3 text-center text-slateish">
                        El manifiesto no contiene desglose de productos.
                      </td>
                    </tr>
                  ) : (
                    sources.map((source) => (
                      <tr key={source.source_product} className="border-b border-ink-700/50">
                        <td className="py-1.5 pr-2 font-mono text-[9px] text-slate-200">{source.source_product}</td>
                        <td className="py-1.5 pr-2 text-slate-200">{source.sensor}</td>
                        <td className="num py-1.5 pr-2 text-slateish">
                          {source.start} → {source.end}
                        </td>
                        <td className="num py-1.5 text-right text-slate-200">{formatNumber(source.records)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge tone="positive">{provenance?.data_mode === 'real' ? 'Dataset real' : 'Muestra'}</Badge>
            <Badge tone="neutral">{meta.dataset_version ?? 'sin versión'}</Badge>
            <Badge tone="ember">{meta.provinces.length} provincias</Badge>
          </div>
          <p className="mt-3 text-[10px] leading-relaxed text-slateish">
            FuegoClaro no es un producto oficial de NASA. Antes de tomar decisiones operativas, verifica siempre los
            productos oficiales.
          </p>
        </Card>

        <Card>
          <SectionHeading
            eyebrow="Qué significa una anomalía"
            title="Inusual no es lo mismo que peligroso"
            description="El radar de anomalías busca días fuera de lo habitual. No explica la causa ni confirma un incendio."
          />
          <div className="space-y-2 text-[11px] leading-relaxed text-slateish">
            <p>
              <span className="font-semibold text-slate-200">Qué comparamos:</span> el número de detecciones de un día
              con la misma época de años anteriores.
            </p>
            <p>
              <span className="font-semibold text-slate-200">Qué significa:</span> que el conteo fue más alto o más bajo
              de lo esperado para esa fecha, región y sensor.
            </p>
            <p>
              <span className="font-semibold text-slate-200">Qué no significa:</span> que haya más fuego. También puede
              cambiar por nubosidad, cobertura del satélite o ajustes del algoritmo.
            </p>
          </div>
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge tone="neutral">
              <Sigma size={10} /> z-score
            </Badge>
            <Badge tone="neutral">control FDR</Badge>
            <Badge tone="warning">No causal</Badge>
          </div>
        </Card>
      </div>

      <Card className="mt-4">
        <SectionHeading
          eyebrow="Proceso"
          title="De los satélites al tablero, en simple"
          description="Cada etapa es explícita y reproducible. No se aplican modelos de lenguaje ni correcciones inventadas."
        />
        <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
          {SIMPLE_STEPS.map((step, index) => (
            <div key={step.title} className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
              <div className="flex items-center gap-2">
                <span className="num flex h-5 w-5 items-center justify-center rounded-md border border-ember-400/30 bg-ember-500/10 text-[9px] font-semibold text-ember-200">
                  {String(index + 1).padStart(2, '0')}
                </span>
                <p className="text-[11px] font-semibold text-white">{step.title}</p>
              </div>
              <p className="mt-1.5 text-[10px] leading-relaxed text-slateish">{step.detail}</p>
            </div>
          ))}
        </div>
      </Card>

      <div className="mt-4 grid gap-3 md:grid-cols-2">
        <Notice tone="critical" title="Lo que este tablero no dice" icon={ShieldCheck}>
          <ul className="space-y-1">
            <li>• Detección de foco de calor ≠ incendio confirmado ≠ superficie quemada.</li>
            <li>• La ausencia de detección no implica ausencia de fuego (nubes, humo, geometría).</li>
            <li>• Los conteos MODIS y VIIRS no son comparables como área ni gravedad.</li>
            <li>• Una anomalía no explica la causa del cambio.</li>
            <li>• Los datos dependen de la cobertura histórica y de la calidad de cada sensor.</li>
          </ul>
        </Notice>
        <Notice tone="info" title="Atribución y uso" icon={CheckCircle2}>
          Fuente: NASA FIRMS. MODIS Collection 6.1 y VIIRS 375 m. Límites administrativos: Natural Earth 1:10m. Fondo de
          mapa: CARTO / OpenStreetMap. Este proyecto es una herramienta de exploración y no está avalado por NASA.
        </Notice>
      </div>

      <details className="panel group mt-4 p-4 sm:p-5">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div>
            <p className="eyebrow mb-1">Anexo técnico</p>
            <h2 className="text-base font-semibold text-white sm:text-lg">
              Fuentes, pipeline y reproducibilidad
            </h2>
            <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slateish">
              Para analistas y desarrolladores: metodología completa, normalización de confianza, API y comandos de
              ejecución.
            </p>
          </div>
          <ChevronDown
            size={18}
            className="shrink-0 text-slateish transition-transform duration-200 group-open:rotate-180"
          />
        </summary>

        <div className="mt-5 space-y-4">
          <Card>
            <SectionHeading eyebrow="Reproducibilidad" title="Archivo y manifiesto" />
            <dl className="space-y-2 text-[11px]">
              <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                <dt className="flex items-center gap-1.5 text-slateish">
                  <Database size={12} /> Archivo
                </dt>
                <dd className="break-all text-right font-mono text-[9px] text-slate-200">
                  {manifest?.file?.path ?? provenance?.path ?? '—'}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                <dt className="flex items-center gap-1.5 text-slateish">
                  <Layers size={12} /> Registros publicados
                </dt>
                <dd className="num text-right text-slate-100">
                  {formatNumber(Number(manifest?.records?.final ?? 0))}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                <dt className="flex items-center gap-1.5 text-slateish">
                  <Globe2 size={12} /> Cobertura
                </dt>
                <dd className="num text-right text-slate-100">
                  {meta.date_range.start} → {meta.date_range.end}
                </dd>
              </div>
              <div className="flex items-start justify-between gap-2 border-b border-ink-700/60 pb-2">
                <dt className="flex items-center gap-1.5 text-slateish">
                  <FileJson size={12} /> Tamaño
                </dt>
                <dd className="num text-right text-slate-100">{bytes(manifest?.file?.bytes)}</dd>
              </div>
              <div className="flex items-start justify-between gap-2">
                <dt className="flex items-center gap-1.5 text-slateish">
                  <Hash size={12} /> SHA-256
                </dt>
                <dd className="break-all text-right font-mono text-[9px] text-slate-200">
                  {manifest?.file?.sha256 ?? '—'}
                </dd>
              </div>
            </dl>
            <div className="mt-3">
              <Notice tone="neutral" title="Trazabilidad">
                El manifiesto completo se publica en <code className="rounded bg-black/30 px-1">/api/v1/provenance</code>{' '}
                y en <code className="rounded bg-black/30 px-1">data/processed/manifest.json</code>. Incluye hashes,
                transformaciones y limitaciones.
              </Notice>
            </div>
          </Card>

          <Card>
            <SectionHeading
              eyebrow="Pipeline"
              title="De la API de NASA FIRMS al tablero"
              description="Cada etapa es explícita y reproducible. No se aplican modelos de lenguaje ni correcciones inventadas a los valores originales."
            />
            <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
              {PIPELINE.map((step, index) => (
                <div key={step.title} className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
                  <div className="flex items-center gap-2">
                    <span className="num flex h-5 w-5 items-center justify-center rounded-md border border-ember-400/30 bg-ember-500/10 text-[9px] font-semibold text-ember-200">
                      {String(index + 1).padStart(2, '0')}
                    </span>
                    <p className="text-[11px] font-semibold text-white">{step.title}</p>
                  </div>
                  <p className="mt-1.5 text-[10px] leading-relaxed text-slateish">{step.detail}</p>
                </div>
              ))}
            </div>
          </Card>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <SectionHeading
                eyebrow="Confianza"
                title="Normalización sin falsa equivalencia"
                description="Se conserva la confianza original y se agrega una categoría normalizada para filtros. Las categorías no son intercambiables entre sensores."
              />
              <div className="space-y-2">
                {CONFIDENCE_ROWS.map((row) => (
                  <div key={row.sensor} className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
                    <div className="flex items-center justify-between">
                      <p className="text-xs font-semibold text-white">{row.sensor}</p>
                      <Badge tone={row.sensor === 'MODIS' ? 'warning' : 'critical'}>{row.original}</Badge>
                    </div>
                    <p className="mt-1 text-[10px] text-slate-200">{row.mapping}</p>
                    <p className="mt-1 text-[9px] leading-relaxed text-slateish">{row.note}</p>
                  </div>
                ))}
              </div>
            </Card>

            <Card>
              <SectionHeading
                eyebrow="Estadística"
                title="Detección de anomalías"
                description="El radar no identifica incendios: identifica días cuyo conteo de detecciones se aparta de lo esperado para esa fecha, región y sensor."
              />
              <div className="space-y-2 text-[11px] leading-relaxed text-slateish">
                <p>
                  <span className="font-semibold text-slate-200">Línea base:</span> para cada día evaluado se usan los
                  días de la misma fecha ± 7 días en años anteriores disponibles, excluyendo el año evaluado.
                </p>
                <p>
                  <span className="font-semibold text-slate-200">Estadístico:</span> z = (observado − media) / desviación
                  estándar de la línea base. p-valor normal bilateral.
                </p>
                <p>
                  <span className="font-semibold text-slate-200">Múltiples pruebas:</span> Benjamini-Hochberg controla la
                  tasa de falsos descubrimientos (FDR) al nivel configurado.
                </p>
                <p>
                  <span className="font-semibold text-slate-200">Mínimos:</span> al menos 3 detecciones observadas y 10
                  días de línea base. Con menos de dos años de historia no se generan pruebas.
                </p>
              </div>
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Badge tone="neutral">
                  <Sigma size={10} /> z-score
                </Badge>
                <Badge tone="neutral">p-valor bilateral</Badge>
                <Badge tone="neutral">FDR Benjamini-Hochberg</Badge>
              </div>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="API"
                title="Endpoints públicos de la base"
                description="Documentación interactiva en /docs del backend. Todas las respuestas incluyen metadatos de procedencia y notas cuando aplica."
              />
              <div className="overflow-x-auto">
                <table className="w-full text-left text-[10px]">
                  <thead>
                    <tr className="border-b border-ink-700 text-[9px] uppercase tracking-wider text-slateish">
                      <th className="py-1.5 pr-2 font-medium">Método</th>
                      <th className="py-1.5 pr-2 font-medium">Ruta</th>
                      <th className="py-1.5 font-medium">Descripción</th>
                    </tr>
                  </thead>
                  <tbody>
                    {ENDPOINTS.map(([method, path, description]) => (
                      <tr key={path} className="border-b border-ink-700/50">
                        <td className="py-1.5 pr-2">
                          <span className="rounded border border-emerald-400/25 bg-emerald-400/10 px-1 py-0.5 text-[8px] font-semibold text-emerald-200">
                            {method}
                          </span>
                        </td>
                        <td className="py-1.5 pr-2 font-mono text-[9px] text-slate-200">{path}</td>
                        <td className="py-1.5 text-slateish">{description}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card>
              <SectionHeading eyebrow="Ejecución local" title="Comandos de referencia" />
              <div className="space-y-2">
                <div className="rounded-lg border border-ink-700 bg-ink-950/70 p-2.5">
                  <p className="mb-1 flex items-center gap-1 text-[9px] uppercase tracking-wider text-slateish">
                    <Terminal size={10} /> Backend
                  </p>
                  <code className="block text-[10px] leading-relaxed text-emerald-200/90">
                    cd backend
                    <br />
                    .venv/bin/uvicorn app.main:app --reload --port 8000
                  </code>
                </div>
                <div className="rounded-lg border border-ink-700 bg-ink-950/70 p-2.5">
                  <p className="mb-1 flex items-center gap-1 text-[9px] uppercase tracking-wider text-slateish">
                    <Terminal size={10} /> Frontend
                  </p>
                  <code className="block text-[10px] leading-relaxed text-emerald-200/90">
                    cd frontend
                    <br />
                    npm install
                    <br />
                    npm run dev
                  </code>
                </div>
                <div className="rounded-lg border border-ink-700 bg-ink-950/70 p-2.5">
                  <p className="mb-1 flex items-center gap-1 text-[9px] uppercase tracking-wider text-slateish">
                    <Terminal size={10} /> Ingesta
                  </p>
                  <code className="block text-[10px] leading-relaxed text-emerald-200/90">
                    cd backend
                    <br />
                    .venv/bin/python ../scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12
                  </code>
                </div>
              </div>
              <p className="mt-2 flex items-start gap-1 text-[9px] leading-relaxed text-slateish">
                <GitBranch size={10} className="mt-0.5 shrink-0" />
                El archivo <code className="rounded bg-black/30 px-1">backend/.env</code> nunca se versiona. La clave no se
                envía al navegador.
              </p>
            </Card>
          </div>

          {manifest?.transformations && (
            <Card>
              <SectionHeading eyebrow="Manifiesto" title="Transformaciones registradas" />
              <ul className="grid gap-1.5 text-[10px] leading-relaxed text-slateish sm:grid-cols-2">
                {manifest.transformations.map((item) => (
                  <li key={item} className="flex gap-1.5">
                    <Braces size={11} className="mt-0.5 shrink-0 text-ember-300/70" />
                    {item}
                  </li>
                ))}
              </ul>
            </Card>
          )}

          {meta.limitations.length > 0 && (
            <Card>
              <SectionHeading eyebrow="Dataset" title="Limitaciones declaradas por el manifiesto" />
              <ul className="space-y-1.5 text-[10px] leading-relaxed text-slateish">
                {meta.limitations.map((item) => (
                  <li key={item} className="flex gap-1.5">
                    <span className="mt-1 h-1 w-1 shrink-0 rounded-full bg-ember-400" />
                    {item}
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
      </details>
    </div>
  )
}
