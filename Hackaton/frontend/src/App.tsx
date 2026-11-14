import { Flame, LoaderCircle } from 'lucide-react'
import { Route, Routes } from 'react-router-dom'
import { FiltersProvider } from './context/FiltersContext'
import { useApi } from './hooks/useApi'
import { Layout } from './components/layout/Layout'
import { ErrorState } from './components/ui/Primitives'
import type { Meta } from './types/api'
import DashboardPage from './pages/DashboardPage'
import FiresPage from './pages/FiresPage'
import MapPage from './pages/MapPage'
import CalendarPage from './pages/CalendarPage'
import ComparePage from './pages/ComparePage'
import AnomaliesPage from './pages/AnomaliesPage'
import FindingsPage from './pages/FindingsPage'
import MethodologyPage from './pages/MethodologyPage'
import NotFoundPage from './pages/NotFoundPage'

function Splash() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4">
      <span className="relative flex h-14 w-14 items-center justify-center rounded-2xl border border-ember-400/30 bg-ember-500/10 text-ember-300 shadow-ember">
        <Flame size={26} strokeWidth={1.7} />
        <span className="absolute -right-1 -top-1 h-2.5 w-2.5 animate-pulse-soft rounded-full bg-ember-400" />
      </span>
      <div className="text-center">
        <p className="text-lg font-semibold text-white">FuegoClaro</p>
        <p className="mt-1 flex items-center gap-2 text-xs text-slateish">
          <LoaderCircle size={13} className="animate-spin" /> Cargando datos y metadatos de NASA FIRMS…
        </p>
      </div>
    </div>
  )
}

export default function App() {
  const { data: meta, loading, error, refetch } = useApi<Meta>('/meta')

  if (loading) return <Splash />
  if (error || !meta) {
    return (
      <div className="mx-auto flex min-h-screen max-w-3xl items-center px-4">
        <div className="w-full">
          <ErrorState
            message={
              error ??
              'No se recibieron metadatos. Verifica que el backend esté corriendo en http://localhost:8000 y que exista un dataset o muestra.'
            }
            onRetry={refetch}
          />
        </div>
      </div>
    )
  }

  return (
    <FiltersProvider meta={meta}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<DashboardPage />} />
          <Route path="incendios" element={<FiresPage />} />
          <Route path="mapa" element={<MapPage />} />
          <Route path="calendario" element={<CalendarPage />} />
          <Route path="comparador" element={<ComparePage />} />
          <Route path="anomalias" element={<AnomaliesPage />} />
          <Route path="hallazgos" element={<FindingsPage />} />
          <Route path="metodologia" element={<MethodologyPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Route>
      </Routes>
    </FiltersProvider>
  )
}
