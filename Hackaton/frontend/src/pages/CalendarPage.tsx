import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Compass,
  Download,
  Filter,
  Flame,
  Gauge,
  Info,
  TrendingUp,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/layout/Layout'
import { FiltersBar } from '../components/layout/FiltersBar'
import {
  Badge,
  Card,
  EmptyState,
  ErrorState,
  LoadingBlock,
  Notice,
  SectionHeading,
  StatCard,
} from '../components/ui/Primitives'
import { useFilters } from '../context/FiltersContext'
import { useApi } from '../hooks/useApi'
import { SENSOR_COLORS } from '../lib/constants'
import { addMonths, formatDate, formatMonth, formatNumber, formatPercent } from '../lib/format'
import { exportUrl } from '../services/api'
import type { ApiEnvelope, CalendarData, CalendarDay } from '../types/api'

const WEEKDAYS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']

function monthStart(month: string): string {
  return `${month}-01`
}

function monthEnd(data: CalendarData | undefined, month: string): string {
  if (data?.end) return data.end
  const [year, monthNumber] = month.split('-').map(Number)
  return `${month}-${String(new Date(year, monthNumber, 0).getDate()).padStart(2, '0')}`
}

export default function CalendarPage() {
  const { meta, filters, apiPath, regionName, setDay, viewMode, setViewMode } = useFilters()
  const [month, setMonth] = useState(() =>
    (meta.date_range.end ?? filters.end ?? new Date().toISOString().slice(0, 10)).slice(0, 7),
  )
  const [selected, setSelected] = useState<CalendarDay | null>(null)

  const calendarState = useApi<ApiEnvelope<CalendarData>>(
    apiPath('/calendar', { month }),
  )
  const calendar = calendarState.data?.data

  const minMonth = (meta.date_range.start ?? month).slice(0, 7)
  const maxMonth = (meta.date_range.end ?? month).slice(0, 7)
  const canGoPrevious = month > minMonth
  const canGoNext = month < maxMonth

  const leadingBlanks = useMemo(() => {
    const [year, monthNumber] = month.split('-').map(Number)
    const weekday = new Date(year, monthNumber - 1, 1).getDay()
    return (weekday + 6) % 7
  }, [month])

  const activeDays = calendar?.days.filter((day) => day.total > 0).length ?? 0
  const average = calendar && activeDays ? calendar.total / calendar.days.length : 0
  const peak = calendar?.days.reduce<CalendarDay | null>(
    (best, day) => (best === null || day.total > best.total ? day : best),
    null,
  )

  const navigate = (delta: number) => {
    setMonth((current) => addMonths(current, delta))
    setSelected(null)
  }

  const isBasic = viewMode === 'basic'

  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow={isBasic ? 'Calendario Ciudadano' : 'Calendario Analítico'}
        title={
          isBasic
            ? `Actividad mensual por día · ${regionName}`
            : `Calendario mensual · ${regionName}`
        }
        description={
          isBasic
            ? 'Registro diario de calor satelital. Cada celda con color indica presencia de anomalías térmicas en la fecha seleccionada.'
            : 'Conteo diario de detecciones por fecha local de adquisición. La intensidad del color representa cantidad de detecciones, nunca superficie quemada. Un día vacío puede deberse a ausencia de fuego o a falta de observación.'
        }
        icon={CalendarDays}
        actions={
          <div className="flex items-center gap-2">
            {isBasic ? (
              <button
                type="button"
                onClick={() => setViewMode('expert')}
                className="focus-ring inline-flex items-center gap-1.5 rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition hover:bg-sky-500/20"
              >
                <Gauge size={14} /> Modo Analista
              </button>
            ) : (
              <a
                href={exportUrl(
                  apiPath('/export/detections.csv', {
                    start_date: monthStart(month),
                    end_date: monthEnd(calendar, month),
                  }),
                )}
                className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
              >
                <Download size={14} /> Exportar mes
              </a>
            )}
          </div>
        }
      />

      <FiltersBar />

      {calendarState.error ? (
        <ErrorState message={calendarState.error} onRetry={calendarState.refetch} />
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard
              label="Total del mes"
              value={formatNumber(calendar?.total ?? 0)}
              sub={formatMonth(month)}
              icon={Flame}
              loading={calendarState.loading && !calendar}
            />
            <StatCard
              label="Días con actividad"
              value={formatNumber(activeDays)}
              sub={`de ${calendar?.days.length ?? 0} días del mes`}
              icon={CalendarDays}
              accent="#3DDC97"
            />
            <StatCard
              label="Promedio diario"
              value={formatNumber(Number(average.toFixed(1)))}
              sub="Detecciones por día calendario"
              icon={TrendingUp}
              accent="#FFB020"
            />
            <StatCard
              label="Día más activo"
              value={peak && peak.total > 0 ? formatNumber(peak.total) : '—'}
              sub={peak && peak.total > 0 ? formatDate(peak.date) : 'Sin detecciones en el mes'}
              icon={Info}
              accent="#FF4D5E"
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_320px]">
            <Card>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => navigate(-1)}
                    disabled={!canGoPrevious}
                    className="focus-ring rounded-lg border border-ink-700 bg-ink-800 p-1.5 text-slateish transition hover:border-ember-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
                    aria-label="Mes anterior"
                  >
                    <ChevronLeft size={15} />
                  </button>
                  <h3 className="min-w-[170px] text-center text-sm font-semibold capitalize text-white">
                    {formatMonth(month)}
                  </h3>
                  <button
                    type="button"
                    onClick={() => navigate(1)}
                    disabled={!canGoNext}
                    className="focus-ring rounded-lg border border-ink-700 bg-ink-800 p-1.5 text-slateish transition hover:border-ember-400/40 hover:text-white disabled:cursor-not-allowed disabled:opacity-35"
                    aria-label="Mes siguiente"
                  >
                    <ChevronRight size={15} />
                  </button>
                </div>
                {!isBasic && (
                  <div className="flex flex-wrap items-center gap-2 text-[10px] text-slateish">
                    <span className="flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full" style={{ background: SENSOR_COLORS.MODIS }} /> MODIS
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="h-2 w-2 rounded-full" style={{ background: SENSOR_COLORS.VIIRS }} /> VIIRS
                    </span>
                    <span className="text-ink-500">·</span>
                    <span>Clic en un día para inspeccionar</span>
                  </div>
                )}
                {isBasic && (
                  <span className="text-xs text-slateish">Haz clic en un día con color para ver detalles</span>
                )}
              </div>

              {calendarState.loading && !calendar ? (
                <LoadingBlock compact label="Cargando calendario…" />
              ) : !calendar ? (
                <EmptyState title="Sin datos de calendario" />
              ) : (
                <>
                  <div className="mb-1.5 grid grid-cols-7 gap-1">
                    {WEEKDAYS.map((weekday) => (
                      <span
                        key={weekday}
                        className="text-center text-[10px] font-semibold uppercase tracking-wider text-slateish"
                      >
                        {weekday}
                      </span>
                    ))}
                  </div>
                  <div className="grid grid-cols-7 gap-1">
                    {Array.from({ length: leadingBlanks }).map((_, index) => (
                      <span key={`blank-${index}`} className="min-h-[72px] rounded-lg" />
                    ))}
                    {calendar.days.map((day) => {
                      const isSelected = selected?.date === day.date
                      const modis = day.by_sensor.MODIS ?? 0
                      const viirs = day.by_sensor.VIIRS ?? 0

                      return (
                        <button
                          key={day.date}
                          type="button"
                          onClick={() => setSelected(day)}
                          title={`${day.date}: ${formatNumber(day.total)} detecciones`}
                          className={`calendar-cell int-${day.intensity} focus-ring ${isSelected ? 'selected' : ''}`}
                        >
                          <span className="flex items-start justify-between">
                            <span className="num text-[11px] font-semibold text-slate-100">{day.day}</span>
                            <span className="num text-[11px] font-semibold text-white">
                              {day.total > 0 ? formatNumber(day.total) : ''}
                            </span>
                          </span>

                          {/* En Modo Experto mostramos los micro-puntos de sensores y % */}
                          {!isBasic ? (
                            <span className="flex items-end justify-between gap-1">
                              <span className="flex gap-0.5">
                                {modis > 0 && (
                                  <span
                                    className="h-1.5 w-1.5 rounded-full"
                                    style={{ background: SENSOR_COLORS.MODIS }}
                                    title={`MODIS: ${formatNumber(modis)}`}
                                  />
                                )}
                                {viirs > 0 && (
                                  <span
                                    className="h-1.5 w-1.5 rounded-full"
                                    style={{ background: SENSOR_COLORS.VIIRS }}
                                    title={`VIIRS: ${formatNumber(viirs)}`}
                                  />
                                )}
                              </span>
                              <span className="text-[9px] leading-none text-slate-200/70">
                                {day.total > 0 ? formatPercent(day.total / (calendar.max_daily || 1)) : ''}
                              </span>
                            </span>
                          ) : (
                            day.total > 0 && (
                              <span className="flex justify-end text-[9px] text-slate-300/80 font-medium">
                                {day.total > 20 ? '🔥 Alto' : day.total > 5 ? 'Medio' : 'Bajo'}
                              </span>
                            )
                          )}
                        </button>
                      )
                    })}
                  </div>
                  <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[10px] text-slateish">
                    <span className="flex items-center gap-1.5">
                      Intensidad:
                      {[1, 2, 3, 4].map((level) => (
                        <span key={level} className={`h-3 w-5 rounded int-${level}`} />
                      ))}
                      <span className="ml-1">más detecciones →</span>
                    </span>
                    <span>Máximo diario del mes: {formatNumber(calendar.max_daily)}</span>
                  </div>
                </>
              )}
            </Card>

            <div className="space-y-3">
              <Card>
                <SectionHeading eyebrow="Día seleccionado" title="Detalle del día" />
                {selected ? (
                  <div className="space-y-3">
                    <div>
                      <p className="text-xs text-slateish">{formatDate(selected.date)}</p>
                      <p className="num mt-1 text-2xl font-semibold text-white">
                        {formatNumber(selected.total)} <span className="text-sm text-slateish">detecciones</span>
                      </p>
                    </div>

                    {!isBasic ? (
                      <div className="space-y-2">
                        <p className="text-[10px] font-bold uppercase tracking-wider text-slateish">
                          Desglose por Sensor Satelital
                        </p>
                        {(['MODIS', 'VIIRS'] as const).map((sensor) => {
                          const value = selected.by_sensor[sensor] ?? 0
                          const share = selected.total > 0 ? (value / selected.total) * 100 : 0
                          return (
                            <div
                              key={sensor}
                              className="flex items-center justify-between rounded-lg border border-ink-700/60 bg-ink-800/50 p-2 text-[11px]"
                            >
                              <span className="flex items-center gap-2 text-slate-200">
                                <span
                                  className="h-2 w-2 rounded-full"
                                  style={{ background: SENSOR_COLORS[sensor] }}
                                />
                                <span className="font-semibold">{sensor}</span>
                                <span className="text-[10px] text-slateish">
                                  {sensor === 'MODIS' ? '~1 km' : '~375 m'}
                                </span>
                              </span>
                              <div className="flex items-center gap-2">
                                <span className="num font-bold text-slate-100">{formatNumber(value)}</span>
                                <span className="num text-[10px] text-slateish">({share.toFixed(0)}%)</span>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    ) : (
                      <div className="rounded-lg border border-ink-700/60 bg-ink-800/40 p-2.5 text-xs text-slateish">
                        <p>
                          Nivel de registro térmico:{' '}
                          <strong className="text-white">
                            {selected.total > 20
                              ? 'Alta actividad'
                              : selected.total > 5
                                ? 'Actividad moderada'
                                : 'Actividad leve o aislada'}
                          </strong>
                        </p>
                      </div>
                    )}

                    <button
                      type="button"
                      onClick={() => setDay(selected.date)}
                      className="focus-ring inline-flex w-full items-center justify-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
                    >
                      <Filter size={13} /> Filtrar este día en toda la app
                    </button>
                    <Link
                      to="/mapa"
                      onClick={() => setDay(selected.date)}
                      className="focus-ring inline-flex w-full items-center justify-center gap-2 rounded-lg border border-ink-700 bg-ink-800/70 px-3 py-2 text-xs font-semibold text-slate-200 transition hover:border-ink-600 hover:text-white"
                    >
                      <Compass size={13} /> Ver este día en el mapa
                    </Link>
                  </div>
                ) : (
                  <div className="py-6 text-center">
                    <span className="mx-auto flex h-10 w-10 items-center justify-center rounded-full border border-ink-600 bg-ink-800 text-slateish">
                      <CalendarDays size={17} />
                    </span>
                    <p className="mt-2 text-xs font-medium text-slate-200">Selecciona un día del calendario</p>
                    <p className="mt-1 text-[10px] leading-relaxed text-slateish">
                      Podrás ver el resumen diario y aplicarlo como filtro global en el mapa y tablero.
                    </p>
                  </div>
                )}
              </Card>

              {isBasic ? (
                <div className="rounded-xl border border-ink-700/60 bg-ink-850/80 p-3.5 text-xs text-slateish leading-relaxed">
                  <p className="font-semibold text-slate-200 mb-1">Nota explicativa:</p>
                  Los días en blanco o con color tenue indican baja o nula presencia de anomalías térmicas captadas en esa fecha. La nubosidad densa puede impedir temporalmente que los sensores vean la superficie.
                </div>
              ) : (
                <>
                  <Notice tone="info" title="Cómo leer el calendario">
                    Cada celda resume un día local. La cifra es un conteo de detecciones y la intensidad es relativa al
                    máximo del mes mostrado. No es área quemada ni cantidad de incendios.
                  </Notice>

                  <Card>
                    <SectionHeading eyebrow="Notas del cálculo" title="Límites" />
                    <ul className="space-y-2 text-[10px] leading-relaxed text-slateish">
                      <li>• Fecha local: UTC-5 en Ecuador continental y UTC-6 en Galápagos.</li>
                      <li>• Un día sin datos puede reflejar nubosidad o falta de pasada del sensor.</li>
                      <li>• Días con intensidad 1 pueden contener pocas detecciones; revisa la cifra exacta.</li>
                    </ul>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                      <Badge tone="neutral">{meta.data_mode === 'real' ? 'Datos reales' : 'Muestra'}</Badge>
                      <Badge tone="ember">{regionName}</Badge>
                    </div>
                  </Card>
                </>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

