import { useFilters } from '../../context/FiltersContext'

export function ProvinceMultiSelect() {
  const { meta, filters, update } = useFilters()
  const selected = (filters.provinces ?? '').split(',').filter(Boolean)
  return (
    <details className="mt-3 rounded-xl border border-ink-700 bg-ink-850/60 p-3">
      <summary className="focus-ring cursor-pointer text-xs font-semibold text-slate-200">
        Seleccionar varias provincias {selected.length > 0 ? `(${selected.length})` : '· Todas'}
      </summary>
      <p className="mt-2 text-xs text-slateish">La selección se combina con los filtros de fecha, sensor y confianza. Al elegir provincias se restablece el territorio a Ecuador.</p>
      <div className="mt-3 grid max-h-52 gap-2 overflow-y-auto sm:grid-cols-2 lg:grid-cols-3">
        {meta.provinces.slice().sort((a, b) => a.name.localeCompare(b.name, 'es')).map((province) => (
          <label key={province.id} className="flex cursor-pointer items-center gap-2 text-xs text-slate-200">
            <input type="checkbox" className="accent-orange-500" checked={selected.includes(province.id)}
              onChange={(event) => update({ region: 'all', provinces: (event.target.checked ? [...selected, province.id] : selected.filter((id) => id !== province.id)).join(',') })} />
            {province.name}
          </label>
        ))}
      </div>
      {selected.length > 0 && <button type="button" className="focus-ring mt-3 text-xs text-ember-300" onClick={() => update({ provinces: '' })}>Quitar selección de provincias</button>}
    </details>
  )
}
