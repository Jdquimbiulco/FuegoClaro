# API (v1)

Base URL por defecto: `http://localhost:8000/api/v1`. Documentación interactiva: `GET /docs`.

Todas las respuestas incluyen metadatos de procedencia/modo de datos cuando aplica. La MAP_KEY nunca se expone.

## Filtros comunes

Usados por la mayoría de endpoints analíticos: `start_date` (YYYY-MM-DD), `end_date`, `region_id` (natural o provincia, `all`/`ecuador`), `sensor` (`MODIS`|`VIIRS`), `confidence` (nivel normalizado), `daynight` (`D`|`N`), `min_frp`.

## Endpoints

- `GET /health` — estado del servicio y dataset.
- `GET /meta` — versión, modo (`real`/`sample`/`empty`), cobertura, sensores/productos, regiones/provincias, limitaciones.
- `GET /regions` — regiones naturales y provincias.
- `GET /regions/geojson` — geometrías provinciales para el mapa.
- `GET /provenance` — manifiesto, hashes, transformaciones y fuentes.
- `GET /detections` — detecciones filtradas. `limit`, `offset`, `order` (`asc`/`desc`), `format` (`json`|`geojson`).
- `GET /detections/{id}` — detalle por id.
- `GET /stats/summary` — indicadores del periodo.
- `GET /stats/timeseries` — `granularity=day|week|month`.
- `GET /calendar` — `month=YYYY-MM`.
- `GET /comparison` — comparación MODIS/VIIRS, `granularity=day|week|month`.
- `GET /anomalies` — `threshold`, `window_days`, `min_observed`, `fdr_alpha`, `max_results`.
- `GET /insights` — hallazgos deterministas trazables.
- `GET /export/detections.csv` — exportación CSV con filtros.

## Notas

- Si el sensor filtrado no tiene datos en el periodo, la respuesta es vacía (no se inventan valores).
- `format=geojson` en detecciones devuelve una `FeatureCollection` para consumo directo en mapas.
- Errores de ingesta/FIRMS no deben producir datasets parciales publicados (la ingesta es estricta).
