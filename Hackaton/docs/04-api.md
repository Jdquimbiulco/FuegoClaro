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
- `GET /fire-events` — eventos espaciotemporales de detecciones. `format=geojson` (por defecto), `dashboard` o `json`; admite `severity`, `province_ids`, `limit` y `offset`.
- `GET /fire-events/{event_id}` — detalle trazable de un evento agrupado.
- `GET /susceptibility` — mapa agregado precalculado; mientras el artefacto no exista devuelve `200` con módulo `pending` y una colección vacía.
- `GET /susceptibility/point` — inferencia puntual; requiere `lat`, `lon`, `date` y admite `window_days=0..7`.
- `GET /analytics/summary` — composición de detecciones, eventos y distribución de riesgo.

## Notas

- Si el sensor filtrado no tiene datos en el periodo, la respuesta es vacía (no se inventan valores).
- `format=geojson` en detecciones devuelve una `FeatureCollection` para consumo directo en mapas.
- Errores de ingesta/FIRMS no deben producir datasets parciales publicados (la ingesta es estricta).
- Los eventos son agrupaciones de detecciones y sus polígonos no representan área quemada. La predicción de riesgo es probabilística y sus bandas dependen del horizonte consultado.
