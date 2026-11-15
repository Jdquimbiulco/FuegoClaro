# Métodos científicos y de datos

## Fuentes y productos

- **NASA FIRMS Area API** sobre Ecuador (bbox `-92.5, -5.5, -74.5, 2.0`).
- **MODIS Collection 6.1** (Terra/Aqua, ~1 km): productos `MODIS_SP` (estándar, priorizado) y `MODIS_NRT`.
- **VIIRS 375 m** (NOAA-20): `VIIRS_NOAA20_SP` y `VIIRS_NOAA20_NRT`.
- Se consulta por bloques de 5 días, con pausas y reintentos; ante rechazo de cuota/MAP_KEY inválida el proceso falla y **no** publica un dataset parcial.

## Normalización canónica

Cada registro se mapea a un esquema único: `id` (hash determinista), producto/sensor/satélite/instrumento, lat/lon, fecha/hora UTC y local, día/noche, confianza original y normalizada, FRP, brillos, `scan/track`, versión, provincia/región y `provenance_id`. Campos originales relevantes se conservan cuando existen.

## Confianza (sin falsa equivalencia)

- **MODIS**: score 0–100 conservado en `confidence_score`; categoría: baja <30, nominal 30–79, alta ≥80.
- **VIIRS**: categorías `l/n/h` → baja/nominal/alta; **no** se inventa score numérico.

## Geografía y tiempo

- Recorte espacial a geometrías provinciales de Ecuador (Natural Earth 1:10m); puntos fuera se excluyen y se contabilizan.
- Asignación de provincia y región natural (Costa, Sierra, Amazonía, Galápagos) por contención geométrica.
- Hora local: UTC-5 continental, UTC-6 Galápagos. La fecha local se usa para calendario y series diarias.

## Validación y deduplicación

- Se descartan (y cuentan): campos obligatorios faltantes, coordenadas inválidas/fuera de rango o (0,0), fecha/hora inválida, duplicados por `id`.
- No se imputan coordenadas, fechas ni valores físicos.

## Agregaciones y comparación

- Resúmenes, series (día/semana/mes), calendario, distribución por sensor/confianza/región/provincia y FRP (sobre valores válidos).
- Comparador: conteos, cobertura temporal, confianza y razón VIIRS/MODIS con la advertencia de que **no** representa área quemada (diferencias de resolución, sensibilidad, algoritmo y pasada).

## Detección de anomalías

- Unidad: conteo diario por región natural y sensor.
- Línea base: misma fecha ±7 días (configurable) en **años anteriores** disponibles, excluyendo el año evaluado.
- Estadístico: z-score `(observado - media) / desviación`; p-valor normal bilateral.
- Múltiples pruebas: control FDR por **Benjamini-Hochberg**.
- Requisitos por defecto: mínimo 3 observados, mínimo 10 días de línea base, |z| ≥ 2.5, FDR ≤ 0.05. Sin ≥2 años de historia no se reportan pruebas concluyentes.
- Interpretación: anomalía = conteo inusual de detecciones, **no** causa ni incendio confirmado; nubosidad/cobertura pueden influir.

## Hallazgos

- Plantillas deterministas sobre agregaciones/comparación/anomalías ya calculadas. Sin LLM para cifras; cada hallazgo incluye indicador, evidencia, método y límite.

## Modelo de riesgo ML

- **Unidad:** celda de 0.1° (~11 km) × día local.
- **Etiqueta:** presencia de evento FIRMS en la celda-día; `y_dh` indica fuego
  exactamente en `D+h` y `y_within_h` en `D..D+h`.
- **Predictores:** FIRMS/eventos con lags y ventanas, clima Open-Meteo, DEM,
  NDVI MOD13Q1, calendario y contexto estático (incluida Galápagos).
- **Fuga:** FIRMS, NDVI y vecindarios se usan hasta `D-1`; para `h>=1` el clima
  también se limita a `D-1` (se excluyen columnas `_d0`).
- **Split temporal:** entrenamiento 2022–2024, validación 2025, prueba 2026,
  restando `h` días al final de cada bloque.
- **Modelo:** `HistGradientBoostingClassifier` por horizonte, con submuestreo
  de negativos solo en entrenamiento y calibración isotónica/logística en
  validación.
- **Niveles:** Bajo/Medio/Alto/Extremo por percentiles p50/p85/p95 de las
  probabilidades calibradas de validación; son relativos, no una norma.
- **Métricas:** ROC-AUC, PR-AUC, Brier, log-loss, precisión/recall/F1,
  precisión y captura en el top k, y baselines de climatología, persistencia y
  regresión logística.
- **Galápagos:** se incluye con `is_galapagos` y `dist_volcano_km`; la
  actividad volcánica exige reportar métricas separadas.

Detalle y comandos: [`07-ml-risk.md`](07-ml-risk.md).

## Limitaciones globales

- Detección ≠ incendio confirmado ≠ superficie quemada.
- Ausencia de detección ≠ ausencia de fuego.
- Productos SP/NRT pueden diferir; la procedencia se documenta por registro.
- Resultados condicionados a la cobertura y calidad histórica disponible.
