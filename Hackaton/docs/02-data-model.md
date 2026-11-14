# Modelo de datos canónico

El dataset publicado es `data/processed/detections.csv`, acompañado de `data/processed/manifest.json`.

## Campos principales

| Campo | Descripción |
| --- | --- |
| `id` | Hash determinista de producto, satélite, fecha, hora y coordenadas. |
| `source_product` | `MODIS_SP`, `MODIS_NRT`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA20_NRT`. |
| `sensor` | `MODIS` o `VIIRS`. |
| `satellite` / `instrument` | Plataforma e instrumento normalizados. |
| `latitude` / `longitude` | Centro del píxel en WGS84. |
| `acq_date` / `acq_time` | Fecha y hora UTC originales (hora `HHMM`). |
| `acquired_at_utc` | Timestamp UTC combinado. |
| `acq_date_local` / `acq_time_local` | Fecha/hora local (UTC-5 continental, UTC-6 Galápagos). |
| `daynight` | `D` o `N` según el producto. |
| `confidence_raw` | Valor original de confianza. |
| `confidence_level` | `low`, `nominal`, `high` o `unknown`. |
| `confidence_score` | Score numérico solo para MODIS; `null` para VIIRS. |
| `frp` | Fire Radiative Power (MW), si está disponible. |
| `brightness` | Brillo MODIS o `bright_ti4` VIIRS. |
| `bright_t31` / `bright_ti5` | Temperaturas de brillo del canal correspondiente. |
| `scan` / `track` | Tamaño del píxel (km) cuando existe. |
| `version` / `type` | Versión del producto y tipo de detección originales. |
| `province` / `province_id` | Provincia asignada por contención geométrica. |
| `region` / `region_id` | Región natural: Costa, Sierra, Amazonía o Galápagos. |
| `provenance_id` | Identificador de la ejecución de ingesta. |

## Confianza

- **MODIS**: `confidence_score` 0–100; `low` <30, `nominal` 30–79, `high` ≥80.
- **VIIRS**: `l/n/h` → `low/nominal/high`; no se crea un score numérico.

## Manifiesto

Incluye `dataset_version`, `generated_at`, `source`, `source_url`, `attribution`, `requested_period`, `bbox`, `sources` (producto, rango, registros), `availability`, `records` (conteos y exclusiones), `date_range`, `fields`, `transformations`, `limitations`, `file` (ruta, SHA-256, bytes) y `warnings`.

## Modos de datos

- `real`: `data/processed/detections.csv` válido.
- `sample`: muestra auténtica en `data/samples/`.
- `empty`: sin datos; la UI lo indica y no inventa cifras.
