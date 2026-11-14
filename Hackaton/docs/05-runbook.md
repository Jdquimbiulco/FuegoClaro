# Runbook operativo

## Arranque local

1. Backend: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000`
2. Frontend: `cd frontend && npm run dev` → http://localhost:5173
3. CORS permitido por defecto: `http://localhost:5173,http://127.0.0.1:5173` (ajustar `CORS_ORIGINS` en `backend/.env`).

## Actualizar datos

```bash
backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw
```

- Requiere `FIRMS_MAP_KEY` en `backend/.env`.
- Productos SP priorizados; NRT solo tras cobertura SP. Segmentación/pausas para respetar cuota.
- Salidas: `data/processed/detections.csv`, `data/processed/manifest.json`, historial en `data/manifests/`, muestra en `data/samples/`.
- **No publica parciales**: si FIRMS falla (p.ej. cuota `Invalid MAP_KEY`), el script aborta y el dataset previo permanece.

## Verificación rápida

- Manifest/cobertura:
  ```bash
  python3 - <<'PY'
  import json; m=json.load(open('data/processed/manifest.json'))
  print(m['date_range'], m['records']['by_sensor'], m['records']['by_source_product'])
  PY
  ```
- Integridad del CSV/manifiesto: `backend/.venv/bin/python scripts/check_dataset.py`.
- API smoke: `GET /api/v1/health`, `/meta`, `/stats/summary`, `/comparison`, `/anomalies`.
- Pruebas: `backend/.venv/bin/python -m pytest -q`.
- Frontend: `cd frontend && npx tsc -b && npm run build`.

## Problemas comunes

- **`Invalid MAP_KEY` / cuota FIRMS**: la API devuelve 400 por exceso de transacciones; el cliente reintenta con esperas largas. Reintentar más tarde o con otra clave válida; revisar que no haya procesos de ingesta paralelos.
- **Sin datos / modo vacío o muestra**: ejecutar ingesta real o confirmar que `data/processed/detections.csv` y `manifest.json` existan y sean coherentes.
- **Cobertura incompleta por sensor**: comparar `date_by_sensor`/`sources` en `/meta` y manifiesto; indica disponibilidad real de productos, no un error de UI.
- **GeoJSON provincial ausente**: regenerar con `backend/.venv/bin/python scripts/build_regions.py`.
- **Frontend no conecta**: verificar `VITE_API_BASE_URL`, que el backend esté en el puerto esperado y CORS.

## Notas de despliegue (base)

- Mantener la clave solo en variables de entorno del backend; nunca en el bundle del frontend.
- Servir frontend estático apuntando al API; para demo offline puede usarse el modo muestra.
- Revisar tamaño del bundle y considerar code-splitting si se optimiza para producción.
