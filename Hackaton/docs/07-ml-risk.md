# Modelo de riesgo de incendios (ML)

Este documento describe el pipeline de machine learning que convierte el
histórico de detecciones NASA FIRMS en un **dataset supervisado** y un
**modelo de probabilidad de incendio** para una ubicación y una fecha.

> **Aviso:** el modelo estima la probabilidad de que exista una detección de
> foco de calor en una celda y ventana determinadas. Una detección **no** es un
> incendio confirmado ni superficie quemada, y la ausencia de detección **no**
> implica ausencia de fuego.

## Alcance

- Genera un dataset por **celda de 0.1° (~11 km) × día local**.
- Cubre el mismo periodo que las detecciones: **2022-01-01 → 2026-11-12**.
- Incluye Galápagos con la bandera `is_galapagos` y distancia a volcanes.
- Entrena **un modelo por horizonte** `h = 0..7` días.
- Entrega dataset, modelo calibrado, umbrales y scripts de inferencia.
- **No** incluye endpoint REST ni interfaz web en esta fase.

## Unidad y targets

Cada fila es una celda y un día local. Para una fecha `D`:

| Columna | Significado |
| --- | --- |
| `y_d0` | Fuego exactamente en `D`. |
| `y_d1` | Fuego exactamente en `D+1`. |
| … | … |
| `y_d7` | Fuego exactamente en `D+7`. |
| `y_within_0` | Fuego en `D`. |
| `y_within_h` | Fuego en al menos uno de `D..D+h`. |

`h=0` es riesgo del mismo día; `h=7` es riesgo a una semana. Los últimos días
del periodo quedan con target `NaN` porque su ventana futura no está completa;
esas filas se excluyen del entrenamiento/evaluación de ese horizonte.

## Fuentes externas

| Fuente | Uso | Credencial |
| --- | --- | --- |
| NASA FIRMS (`data/processed/detections.csv`) | Histórico de detecciones y eventos. | `FIRMS_MAP_KEY` solo para ingesta. |
| NASA POWER | Clima diario histórico. | No requiere clave. |
| DEM local (Copernicus GLO-30) | Elevación, pendiente, aspecto y rugosidad. | No requiere clave. |
| NASA AppEEARS MOD13Q1.061 | NDVI de 250 m cada 16 días. | `EARTHDATA_TOKEN` (o usuario/clave). |

Las fuentes se consultan en el **centro de cada celda**. Todas las descargas se
cachean en `data/cache/` y son reanudables.

### NDVI con AppEEARS

1. Crea un token en <https://urs.earthdata.nasa.gov/>.
2. Copia `backend/.env.example` a `backend/.env` y define `EARTHDATA_TOKEN=...`
   (nunca versiones el token).
3. Ejecuta el build sin `--skip-ndvi`.
4. Si no hay token o una tarea falla, el dataset se genera igualmente con
   `ndvi_available=0` y una advertencia en el manifiesto.

El pipeline usa tareas `point` de `MOD13Q1.061`, capas
`250m_16_days_NDVI` y `250m_16_days_pixel_reliability`, en bloques de 500
puntos. Los compuestos se convierten a serie diaria por *forward fill* y se
cruzan con `D-1` para no filtrar información del día objetivo.

## Variables

### Actividad FIRMS y eventos

- Conteos diarios: `det_count`, `event_count`, `event_det_count`.
- FRP: `frp_sum`, `frp_max`, `event_frp_sum`, `event_frp_max`.
- Composición: `night_count`, `high_conf_count`, `modis_count`, `viirs_count`,
  `mean_hour`, `event_alert_max`, `event_points_max`.
- Lags 1/2/3/7 días y ventanas móviles 3/7/14/30 días.
- Días desde el último fuego (`days_since_fire`) y días con fuego en 30 días.
- Vecindarios 3×3 y 5×5: suma de detecciones/FRP/eventos, vecinos activos y
  distancia a la celda con fuego más cercana.

Los estadísticos de evento (`event_frp_*`, `event_points_max`, etc.) se
calculan por **celda-día**, no con el total del evento completo, para no usar
puntos futuros del mismo evento. `event_count` y `event_alert_max` se guardan
para auditoría, pero se excluyen del modelo por depender del evento completo.

### Clima

Temperatura máxima/mínima/media, humedad media/mínima, viento y rachas,
precipitación, VPD, ET0, humedad del suelo (0–7 cm y 7–28 cm) y radiación.
Se generan lags y medias móviles de 7/30 días, días secos consecutivos,
anomalía de temperatura a 30 días y razón precipitación/ET0.

### Estáticos y contexto

Elevación, pendiente, aspecto, rugosidad, provincia/región codificadas,
frecuencia histórica de fuego por celda/provincia-mes/región-mes, distancia a
fuego histórico y distancia al volcán galapagueño más cercano.

### Calendario

Mes, día del año, semana, día de la semana, fin de semana y codificación
cíclica del día del año.

## Control de fuga de información

| Horizonte | FIRMS/eventos | Clima | NDVI | Calendario |
| --- | --- | --- | --- | --- |
| `h=0` | Hasta `D-1` | `D` (más lags) | Hasta `D-1` | `D` |
| `h>=1` | Hasta `D-1` | Hasta `D-1` (se excluyen columnas `_d0`) | Hasta `D-1` | `D` |

- Los vecindarios y lags se desplazan al menos un día.
- Las columnas crudas de clima (`wx_*` sin sufijo) y NDVI del mismo día se
  excluyen; solo se usan sus versiones `_d0` (h=0) o con lag/ventana.
- Los agregados de evento se calculan por celda-día y `event_count`/
  `event_alert_max` se excluyen del modelo.
- Las frecuencias históricas se calculan **solo con 2022–2024**.
- El split temporal usa **8 días de separación efectiva** al restar `h` días al
  final de cada bloque.

## Partición temporal

| Bloque | Periodo | Uso |
| --- | --- | --- |
| Entrenamiento | 2022-01-01 → 2024-12-31 − `h` días | Ajuste del modelo. |
| Validación | 2025-01-01 → 2025-12-31 − `h` días | Calibración y umbrales. |
| Prueba | 2026-01-01 → último día − `h` días | Evaluación final. |

## Modelo y calibración

- Algoritmo: `HistGradientBoostingClassifier` de scikit-learn, un modelo por
  horizonte.
- Desbalance: en entrenamiento se conservan todos los positivos y se
  submuestrean negativos (5:1 para h≤1, 3:1 para h=2..4 y 2:1 para h=5..7 por
  defecto). La evaluación se hace sobre el panel completo de prueba.
- Calibración: isotónica sobre validación (logística si hay menos de 200
  positivos). Se devuelve probabilidad absoluta calibrada.
- Umbrales de nivel: percentiles **p50/p85/p95** de las probabilidades
  calibradas de validación, por horizonte, guardados en
  `risk_thresholds.json`.

| Nivel | Regla |
| --- | --- |
| Bajo | `p <= p50` |
| Medio | `p50 < p <= p85` |
| Alto | `p85 < p <= p95` |
| Extremo | `p > p95` |

Los niveles son **relativos a la distribución de validación** y pueden variar
entre horizontes. La probabilidad absoluta también se devuelve y debe
interpretarse junto con la calibración y la cobertura de datos.

## Métricas y baselines

Se calculan en prueba: ROC-AUC, PR-AUC, Brier, log-loss, precisión/recall/F1 en
umbrales 0.1/0.2/0.3/0.5, precisión y captura en el top 1 %, 5 % y 10 %.
También se comparan tres baselines:

- **Climatología por celda:** frecuencia histórica de fuego 2022–2024.
- **Persistencia FIRMS:** indica si hubo detección en `D-1`.
- **Regresión logística:** mismas variables, con imputación mediana y escalado.

La importancia de variables se estima por permutación (PR-AUC) sobre una
muestra de prueba y se guarda en `risk_feature_importance.csv`. Puede omitirse
con `--skip-importance`.

## Galápagos

Galápagos se incluye con `is_galapagos=1` y `dist_volcano_km`. La actividad
volcánica puede producir detecciones térmicas que no son incendios. Se
recomienda reportar métricas separadas para Galápagos y no interpretar sus
niveles como riesgo de incendio convencional.

## Comandos

Desde `Hackaton/` y con el entorno del backend activo:

```bash
# 1. Dataset completo con clima, DEM y NDVI (requiere EARTHDATA_TOKEN)
backend/.venv/bin/python scripts/build_fire_risk_dataset.py \
  --start 2022-01-01 --end 2026-11-12

# Variante sin NDVI (si no hay token)
backend/.venv/bin/python scripts/build_fire_risk_dataset.py --skip-ndvi

# Prueba rápida sin fuentes externas
backend/.venv/bin/python scripts/build_fire_risk_dataset.py \
  --limit-cells 100 --skip-weather --skip-dem --skip-ndvi

# 2. Entrenamiento de los 8 horizontes
backend/.venv/bin/python scripts/train_fire_risk_model.py

# Variante rápida para validar el pipeline
backend/.venv/bin/python scripts/train_fire_risk_model.py \
  --horizons 0,7 --quick --skip-importance

# 3. Inferencia puntual
backend/.venv/bin/python scripts/predict_fire_risk.py \
  --lat -4.4161 --lon -79.54454 --date 2026-11-20 --window-days 7

# 4. Inferencia por lote (CSV: latitude,longitude,date[,window_days])
backend/.venv/bin/python scripts/predict_fire_risk.py \
  --batch entradas.csv --output salidas.csv
```

En Windows, reemplaza `backend/.venv/bin/python` por
`backend\.venv\Scripts\python.exe`.

## Salidas

En `data/processed/ml/`:

| Archivo | Contenido |
| --- | --- |
| `fire_risk_dataset.parquet` | Panel completo con variables y targets. |
| `fire_risk_dataset.meta.json` | Manifiesto, grupos de variables, faltantes, chequeos de fuga y advertencias. |
| `fire_events_history.parquet` | Eventos históricos generados por `detect_fire_events()`. |
| `cells_static.parquet` | Atributos estáticos por celda. |
| `cell_day_aggregates.parquet` | Agregados FIRMS/clima por celda-día para auditoría. |
| `weather_daily.parquet` / `ndvi_daily.parquet` | Series externas cacheadas. |
| `risk_model.joblib` | Modelos calibrados, columnas y umbrales. |
| `risk_model_metrics.json` | Métricas de validación/prueba y baselines. |
| `risk_thresholds.json` | Umbrales p50/p85/p95 por horizonte. |
| `risk_feature_columns.json` | Variables usadas por cada horizonte. |
| `risk_feature_importance.csv` | Importancia por permutación (si se calculó). |

El dataset completo esperado es de aproximadamente **3,53 millones de filas**
(≈2.066 celdas terrestres × 1.709 días). El tamaño en disco depende de las
fuentes externas disponibles.

## Limitaciones

- FIRMS detecta focos de calor, no incendios confirmados; la cobertura depende
  de nubosidad, sensor y pasada.
- MODIS y VIIRS no son directamente comparables; el modelo usa el histórico
  armonizado y documenta la procedencia.
- La etiqueta es presencia/ausencia de detección en la celda-día, no área
  quemada ni severidad.
- El clima de reanálisis y el NDVI tienen resolución/incertidumbre propias.
- Los niveles Bajo/Medio/Alto/Extremo son relativos a la validación 2025; no
  son una norma oficial.
- En fechas futuras, la inferencia usa el último estado FIRMS disponible y,
  para `h=0`, el pronóstico del día. No inventa detecciones futuras.
- Galápagos requiere lectura separada por actividad volcánica.
