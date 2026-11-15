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
| `canton` / `canton_id` | Cantón y código DPA asignados por contención con la capa oficial. |
| `region` / `region_id` | Región natural: Costa, Sierra, Amazonía o Galápagos. |
| `provenance_id` | Identificador de la ejecución de ingesta. |

## Confianza

- **MODIS**: `confidence_score` 0–100; `low` <30, `nominal` 30–79, `high` ≥80.
- **VIIRS**: `l/n/h` → `low/nominal/high`; no se crea un score numérico.

## División cantonal

`data/regions/ecuador_cantons.geojson` es el único artefacto territorial
cantonal que se versiona. Contiene 224 polígonos en WGS84, derivados del ZIP
oficial de **Organización Territorial Cantonal** del Ministerio de Gobierno / CONALI.
El shapefile descargado y sus archivos auxiliares (`.shp`, `.dbf`, `.shx`,
`.prj`, etc.) no se copian al repositorio porque la aplicación no los consume.
La capa se simplificó a una tolerancia aproximada de 10 m para reducir su
tamaño; se usa para filtro y presentación, no para deslinde legal.

## Manifiesto

Incluye `dataset_version`, `generated_at`, `source`, `source_url`, `attribution`, `requested_period`, `bbox`, `sources` (producto, rango, registros), `availability`, `records` (conteos y exclusiones), `date_range`, `fields`, `transformations`, `limitations`, `file` (ruta, SHA-256, bytes) y `warnings`.

## Dataset ML de riesgo

`data/processed/ml/fire_risk_dataset.parquet` es un panel por **celda de 0.1° ×
día local** con una fila por celda y fecha. Campos principales:

| Grupo | Ejemplos |
| --- | --- |
| Claves | `cell_id`, `date`, `lat`, `lon`, `province_id`, `region_id`, `is_galapagos`. |
| FIRMS/eventos | `det_count_*`, `frp_*`, `event_*`, lags y ventanas móviles. |
| Vecindario | `det_sum_3x3_lag1`, `frp_sum_5x5_lag1`, `dist_nearest_fire_km`. |
| Clima | `wx_temperature_2m_max_d0`, `wx_*_lag1`, `wx_*_roll7/30`, `dry_days`. |
| DEM | `elevation_m`, `slope_deg`, `aspect_sin/cos`, `terrain_roughness`. |
| NDVI | `ndvi_lag1`, `ndvi_age_days`, `ndvi_quality`, `ndvi_available`. |
| Estáticos | `fire_freq_cell`, `fire_freq_province_month`, `dist_hist_fire_km`. |
| Targets | `y_d0..y_d7`, `y_within_0..y_within_7`. |

El manifiesto `fire_risk_dataset.meta.json` documenta grupos de variables,
faltantes, conteos de positivos, parámetros y chequeos de fuga. Las variables
de clima `_d0` solo se usan en el modelo de horizonte 0. Detalle completo en
[`07-ml-risk.md`](07-ml-risk.md).

## Modos de datos

- `real`: `data/processed/detections.csv` válido.
- `sample`: muestra auténtica en `data/samples/`.
- `empty`: sin datos; la UI lo indica y no inventa cifras.
