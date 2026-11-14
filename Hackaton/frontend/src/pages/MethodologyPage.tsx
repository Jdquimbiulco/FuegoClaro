import {
  BookOpen,
  Braces,
  CheckCircle2,
  Database,
  FileJson,
  GitBranch,
  Globe2,
  Hash,
  Layers,
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
        eyebrow="Metodología y procedencia"
        title="Cómo se construyen los datos y qué no se puede concluir"
        description="FuegoClaro armoniza detecciones de focos de calor MODIS y VIIRS de NASA FIRMS. Esta página documenta fuentes, transformaciones, supuestos, límites y reproducibilidad. No es un producto oficial de NASA."
        icon={BookOpen}
      />

      {provenanceState.error ? (
        <ErrorState message={provenanceState.error} onRetry={provenanceState.refetch} />
      ) : provenanceState.loading && !provenance ? (
        <LoadingBlock label="Cargando procedencia del dataset…" />
      ) : (
        <>
          <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
            <Card>
              <SectionHeading
                eyebrow="Fuente"
                title="NASA FIRMS · MODIS y VIIRS"
                description="Fire Information for Resource Management System. Los productos estándar (SP) se priorizan; los de tiempo casi real (NRT) cubren el tramo reciente y se identifican por registro."
              />
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-[#FFB020]" />
                    <p className="text-xs font-semibold text-white">MODIS Collection 6.1</p>
                  </div>
                  <p className="mt-1 text-[10px] leading-relaxed text-slateish">
                    Terra/Aqua · píxel ~1 km · confianza numérica 0–100 · pasadas diarias con horarios variables.
                  </p>
                </div>
                <div className="rounded-xl border border-ink-700/70 bg-ink-800/40 p-3">
                  <div className="flex items-center gap-2">
                    <span className="h-2 w-2 rounded-full bg-[#FF4D5E]" />
                    <p className="text-xs font-semibold text-white">VIIRS 375 m</p>
                  </div>
                  <p className="mt-1 text-[10px] leading-relaxed text-slateish">
                    NOAA-20 · píxel ~375 m · confianza categórica low/nominal/high · mayor detalle espacial.
                  </p>
                </div>
              </div>
              <div className="mt-3 overflow-x-auto">
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
              <div className="mt-3 flex flex-wrap gap-1.5">
                <Badge tone="positive">{provenance?.data_mode === 'real' ? 'Dataset real' : 'Muestra'}</Badge>
                <Badge tone="neutral">{meta.dataset_version ?? 'sin versión'}</Badge>
                <Badge tone="ember">{meta.provinces.length} provincias</Badge>
              </div>
            </Card>

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
          </div>

          <Card className="mt-4">
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

          <div className="mt-4 grid gap-4 xl:grid-cols-2">
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

          <div className="mt-4 grid gap-4 xl:grid-cols-[1.2fr_1fr]">
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

          <div className="mt-4 grid gap-3 md:grid-cols-2">
            <Notice tone="critical" title="Limitaciones explícitas" icon={ShieldCheck}>
              <ul className="space-y-1">
                <li>• Detección de foco de calor ≠ incendio confirmado ≠ superficie quemada.</li>
                <li>• La ausencia de detección no implica ausencia de fuego (nubes, humo, geometría).</li>
                <li>• Los conteos MODIS y VIIRS no son directamente comparables como área ni gravedad.</li>
                <li>• Los productos SP y NRT pueden diferir; el producto se documenta por registro.</li>
                <li>• La línea base de anomalías depende de la cobertura histórica disponible.</li>
              </ul>
            </Notice>
            <Notice tone="info" title="Atribución y uso" icon={CheckCircle2}>
              Fuente: NASA FIRMS. MODIS Collection 6.1 y VIIRS 375 m. Límites administrativos: Natural Earth 1:10m.
              Fondo de mapa: CARTO / OpenStreetMap. Este proyecto es una herramienta de exploración y no está avalado por
              NASA. Verifica siempre los productos oficiales antes de tomar decisiones operativas.
            </Notice>
          </div>

          {manifest?.transformations && (
            <Card className="mt-4">
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
            <Card className="mt-4">
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
        </>
      )}
    </div>
  )
}
