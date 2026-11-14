import { Compass, Home, Map as MapIcon } from 'lucide-react'
import { Link } from 'react-router-dom'
import { PageHeader } from '../components/layout/Layout'
import { Card } from '../components/ui/Primitives'

export default function NotFoundPage() {
  return (
    <div className="animate-fade-up">
      <PageHeader
        eyebrow="Ruta no encontrada"
        title="Esta vista no existe"
        description="La dirección solicitada no corresponde a ninguno de los módulos de FuegoClaro."
        icon={Compass}
      />
      <Card className="mx-auto max-w-xl text-center">
        <p className="num text-5xl font-semibold text-ember-400">404</p>
        <p className="mt-2 text-sm text-slate-200">
          Puedes volver al panel general o abrir el mapa interactivo.
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
          <Link
            to="/"
            className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ember-400/35 bg-ember-500/10 px-3 py-2 text-xs font-semibold text-ember-100 transition hover:border-ember-300/60"
          >
            <Home size={13} /> Dashboard
          </Link>
          <Link
            to="/mapa"
            className="focus-ring inline-flex items-center gap-2 rounded-lg border border-ink-600 bg-ink-800 px-3 py-2 text-xs font-semibold text-slate-100 transition hover:border-ember-400/40"
          >
            <MapIcon size={13} /> Mapa
          </Link>
        </div>
      </Card>
    </div>
  )
}
