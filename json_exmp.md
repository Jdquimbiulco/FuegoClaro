# Contrato JSON Frontend–Backend v2

**Proyecto:** FuegoClaro — armonización MODIS/VIIRS para Ecuador
**Estado:** listo para revisión
**Fuente de verdad:** este documento
**Plan de implementación:** [`PLAN_IMPLEMENTACION_PERSONA_1.md`](PLAN_IMPLEMENTACION_PERSONA_1.md)

> **Aviso científico:** una detección de foco de calor **no** es un incendio confirmado ni superficie quemada. Un evento agrupado por clustering **no** es área quemada. La ausencia de detecciones no implica ausencia de fuego. Los conteos MODIS y VIIRS no son intercambiables.

---

## 1. Objetivo

Definir los JSON que el backend entrega al frontend para:

1. Detecciones individuales existentes (sin cambios).
2. Eventos de incendio generados por `app.domain.fire_events.detect_fire_events()`.
3. Mapa agregado de susceptibilidad (artefacto) y predicción puntual del modelo ML.
4. Resumen analítico compuesto.

Todos los ejemplos poblados son **ilustrativos**. Los valores reales dependen del dataset (`fuegoclaro-20261113T003529Z`) y del modelo (`fuegoclaro-risk-20261114T225059Z`).

---

## 2. Decisiones de contrato

| Tema | Decisión |
|---|---|
| Formato principal de `/fire-events` | **GeoJSON** (`FeatureCollection`) |
| Formato del feed del dashboard | `format=dashboard` → `FireDashboard` |
| Formato plano | `format=json` → lista de eventos |
| Vocabulario de eventos | **Español**, igual que `frontend/src/types/fire.ts` |
| Predicción puntual | `GET /susceptibility/point` (modelo real en vivo) |
| Mapa agregado | `GET /susceptibility` (artefacto `susceptibility.json`) |
| Módulo no conectado | `200` + `module.status = "pending"` |
| Artefacto inválido | `503` + envelope de error |
| Analytics | Endpoint separado `/analytics/summary` |
| Endpoints legacy | Sin cambios |
| Valores no calculables | `null`, nunca `0` |
| Fechas de evento | `YYYY-MM-DD` (el módulo no devuelve hora) |
| Umbrales de riesgo | **p50/p85/p95 por horizonte**, no bandas fijas |
| Nivel de riesgo | Solo `risk_level` en **español** (`Bajo`, `Medio`, `Alto`, `Extremo`) |
| Enriquecimiento por evento | Calculado en el servicio (`confidence_by_level`, `evidence_score_max`, `context_flags`, `hull_area_km2`) |
| Fecha en predicción puntual | Solo `date`; los rangos se resolverán en el frontend |

---

## 3. Envelope global

```json
{
  "meta": {},
  "pagination": {},
  "data": {}
}
```

- `meta`: procedencia, periodo, filtros, estado del módulo.
- `pagination`: solo en listados paginados.
- `data`: carga útil del endpoint.
- En `format=dashboard`, `data` es exactamente `FireDashboard`.

### 3.1 Envelope de error

```json
{
  "error": {
    "code": "MODULE_UNAVAILABLE",
    "message": "El módulo 'susceptibility' no está disponible.",
    "details": {
      "module": "susceptibility",
      "status": "pending",
      "detail": "No existe data/processed/ml/risk_model.joblib"
    }
  }
}
```

| Código | HTTP | Uso |
|---|---|---|
| `VALIDATION_ERROR` | `422` | Parámetros inválidos (handler existente) |
| `HTTP_ERROR` | `400` | Filtros inválidos vía `HTTPException` |
| `NOT_FOUND` | `404` | Evento puntual inexistente |
| `MODULE_UNAVAILABLE` | `503` | Faltan artefactos del modelo |
| `CONTRACT_ERROR` | `503` | El artefacto no cumple el contrato |
| `INTERNAL_ERROR` | `500` | Error no controlado |

---

## 4. Enums y estados

```json
{"sensors": ["MODIS", "VIIRS"]}
```

```json
{"confidence_levels": ["low", "nominal", "high", "unknown"]}
```

```json
{"alert_levels": ["alerta_roja", "alerta_media", "quema_menor"]}
```

```json
{"module_status": ["pending", "available", "error"]}
```

```json
{"data_mode": ["real", "sample", "empty"]}
```

| `nivel_alerta` | Etiqueta | Color sugerido |
|---|---|---|
| `alerta_roja` | Alerta roja | Rojo |
| `alerta_media` | Alerta media | Naranja |
| `quema_menor` | Quema menor | Amarillo |

| `risk_level` | Color sugerido |
|---|---|
| `Bajo` | Verde |
| `Medio` | Amarillo |
| `Alto` | Naranja |
| `Extremo` | Rojo intenso |

---

## 5. Reglas de `null` vs `0`

| Caso | Valor correcto |
|---|---|
| Periodo sin eventos | `summary.events: 0` |
| Periodo sin detecciones | `summary.detections: 0` |
| FRP no calculable | `frp_total: null` |
| Sin fuente de confirmación | `confirmed_critical: null` |
| Sin agregación cantonal | `extreme_risk_cantons: null` |
| Sin provincia asignada | `canton: null` |
| Sin artefacto de mapa | `module.status: "pending"` |
| Sin modelo cargado | `model_version: null` |
| Sin evidencia calculable | `evidence_score_max: null` |

El frontend debe tratar `null` como “no disponible”, no como “cero”.

---

## 6. `GET /api/v1/fire-events`

### 6.1 Parámetros

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `start_date` | `YYYY-MM-DD` | ventana por defecto | Fecha inicial local |
| `end_date` | `YYYY-MM-DD` | ventana por defecto | Fecha final local |
| `region_id` | `str` | `all` | Región natural, provincia o `all` |
| `sensor` | `str` | `all` | `MODIS`, `VIIRS` o `all` |
| `confidence` | `str` | `null` | Niveles separados por coma |
| `daynight` | `str` | `null` | `D` o `N` |
| `min_frp` | `float` | `null` | FRP mínimo en MW |
| `severity` | `str` | `null` | `alerta_roja`, `alerta_media`, `quema_menor` |
| `province_ids` | `str` | `null` | IDs de provincia separados por coma |
| `granularity` | `str` | `month` | `day`, `week`, `month` (solo dashboard) |
| `format` | `str` | `geojson` | `geojson`, `dashboard`, `json` |
| `limit` | `int` | `500` | Máximo 5000 |
| `offset` | `int` | `0` | Desplazamiento |

### 6.2 `format=geojson` — ejemplo poblado

> Abreviado: 1 evento de 3. No representa datos oficiales.

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31"
    },
    "filters": {
      "region_id": "all",
      "sensor": "all",
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "module": {
      "name": "clustering",
      "status": "available",
      "version": null
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "Los eventos son agrupaciones espaciotemporales de detecciones; no representan superficie quemada confirmada."
    ]
  },
  "pagination": {
    "total": 3,
    "limit": 500,
    "offset": 0,
    "returned": 1,
    "truncated": true
  },
  "data": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Polygon",
          "coordinates": [
            [
              [-79.22, -4.12],
              [-79.1, -4.12],
              [-79.1, -4.0],
              [-79.22, -4.0],
              [-79.22, -4.12]
            ]
          ]
        },
        "properties": {
          "id_evento": "EVT-0001",
          "centro": [-4.06, -79.16],
          "inicio": "2026-08-15",
          "fin": "2026-08-16",
          "dias": ["2026-08-15", "2026-08-16"],
          "nivel_alerta": "alerta_roja",
          "nivel_alerta_label": "Alerta roja",
          "motivo_regla": "FRP total 342.5 MW > 100 MW | detección activa en paso nocturno",
          "provincias": ["loja"],
          "province_names": ["Loja"],
          "region_id": "sierra",
          "region": "Sierra",
          "canton": null,
          "frp_total": 342.5,
          "frp_max": 98.2,
          "frp_medio": 12.69,
          "puntos_count": 27,
          "diurnas": 10,
          "nocturnas": 17,
          "sensores": ["MODIS", "VIIRS"],
          "contraste_medio_k": 46.3,
          "confidence_by_level": {
            "low": 1,
            "nominal": 9,
            "high": 17,
            "unknown": 0
          },
          "confidence_dominant": "high",
          "evidence_score_max": 87,
          "context_flags": [],
          "hull_area_km2": 12.8,
          "rank": 1
        }
      }
    ]
  }
}
```

### 6.3 `format=geojson` — periodo sin eventos

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-11-01",
      "end": "2026-11-02"
    },
    "filters": {
      "region_id": "all",
      "sensor": "all",
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "module": {
      "name": "clustering",
      "status": "available",
      "version": null
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "No se formaron eventos con los filtros aplicados. La ausencia de detecciones no implica ausencia de fuego."
    ]
  },
  "pagination": {
    "total": 0,
    "limit": 500,
    "offset": 0,
    "returned": 0,
    "truncated": false
  },
  "data": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

### 6.4 `format=dashboard` — feed del frontend

Contrato exacto de `frontend/src/types/fire.ts`.

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31"
    },
    "filters": {
      "region_id": "all",
      "sensor": "all",
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "confirmed_critical y extreme_risk_cantons son null porque no existe fuente de confirmación ni agregación cantonal."
    ]
  },
  "data": {
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31"
    },
    "summary": {
      "detections": 1240,
      "events": 12,
      "critical_events": 3,
      "confirmed_critical": null,
      "extreme_risk_cantons": null,
      "frp_total": 842.3
    },
    "events": [
      {
        "id_evento": "EVT-0001",
        "centro": [-4.06, -79.16],
        "inicio": "2026-08-15",
        "fin": "2026-08-16",
        "nivel_alerta": "alerta_roja",
        "motivo_regla": "FRP total 342.5 MW > 100 MW | detección activa en paso nocturno",
        "provincias": ["loja"],
        "province_names": ["Loja"],
        "canton": null,
        "frp_total": 342.5,
        "puntos_count": 27,
        "nocturnas": 17,
        "sensores": ["MODIS", "VIIRS"]
      }
    ],
    "by_province": [
      {"id": "loja", "name": "Loja", "count": 4},
      {"id": "azuay", "name": "Azuay", "count": 2}
    ],
    "series": [
      {
        "period": "2026-08",
        "sensor": "MODIS",
        "count": 260,
        "frp_sum": 240.9,
        "frp_mean": 0.93,
        "active_days": 18
      },
      {
        "period": "2026-08",
        "sensor": "VIIRS",
        "count": 980,
        "frp_sum": 601.4,
        "frp_mean": 0.61,
        "active_days": 20
      }
    ],
    "seasonality": [
      {"period": "2022-09", "count": 410},
      {"period": "2023-09", "count": 388},
      {"period": "2024-09", "count": 502},
      {"period": "2025-09", "count": 461}
    ],
    "history_period": {
      "start": "2022-01-01",
      "end": "2026-11-12"
    },
    "notes": [
      "El feed es exploratorio; no confirma incendios ni cuantifica superficie quemada."
    ]
  }
}
```

### 6.5 `format=json` — tabla plana

`data` es un arreglo de eventos con los mismos campos que `properties`, más `puntos_ids` para trazabilidad.

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31"
    },
    "filters": {
      "region_id": "all",
      "sensor": "all",
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "module": {
      "name": "clustering",
      "status": "available",
      "version": null
    },
    "attribution": "NASA FIRMS",
    "notes": []
  },
  "pagination": {
    "total": 3,
    "limit": 2,
    "offset": 0,
    "returned": 2,
    "truncated": true
  },
  "data": [
    {
      "id_evento": "EVT-0001",
      "frp_total": 342.5,
      "frp_max": 98.2,
      "puntos_count": 27,
      "nivel_alerta": "alerta_roja",
      "inicio": "2026-08-15",
      "fin": "2026-08-16",
      "provincias": ["loja"],
      "puntos_ids": ["7f3c2a1b9d8e4f60", "9a1b2c3d4e5f6789"]
    }
  ]
}
```

### 6.6 `GET /api/v1/fire-events/{event_id}`

Devuelve un solo evento en `format=json`, con `puntos_ids` incluidos. Si no existe:

```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Evento no encontrado: EVT-9999",
    "details": {
      "event_id": "EVT-9999"
    }
  }
}
```

### 6.7 Campos de un evento

| Campo | Tipo | Origen | Descripción |
|---|---|---|---|
| `id_evento` | `string` | módulo | ID determinista del cluster |
| `centro` | `[number, number]` | módulo | `[lat, lon]` medio |
| `inicio` | `string` | módulo | Fecha local `YYYY-MM-DD` |
| `fin` | `string` | módulo | Fecha local `YYYY-MM-DD` |
| `dias` | `string[]` | módulo | Días con detecciones |
| `nivel_alerta` | `string` | módulo | `alerta_roja`, `alerta_media`, `quema_menor` |
| `nivel_alerta_label` | `string` | módulo | Etiqueta legible |
| `motivo_regla` | `string` | módulo | Regla auditable que asignó el nivel |
| `provincias` | `string[]` | módulo | IDs de provincia |
| `province_names` | `string[]` | servicio | Nombres de provincia |
| `region_id` | `string` | servicio | Región natural de la primera provincia |
| `region` | `string` | servicio | Nombre de la región |
| `canton` | `string \| null` | servicio | `null`: sin asignación cantonal |
| `frp_total` | `number` | módulo | Suma de FRP (MW) |
| `frp_max` | `number` | módulo | FRP máximo (MW) |
| `frp_medio` | `number` | módulo | FRP medio (MW) |
| `puntos_count` | `integer` | módulo | Detecciones agrupadas |
| `diurnas` | `integer` | módulo | Detecciones diurnas |
| `nocturnas` | `integer` | módulo | Detecciones nocturnas |
| `sensores` | `string[]` | módulo | Sensores presentes |
| `contraste_medio_k` | `number` | módulo | Contraste térmico medio (K) |
| `confidence_by_level` | `object` | servicio | Conteo por nivel de confianza |
| `confidence_dominant` | `string` | servicio | Nivel dominante |
| `evidence_score_max` | `integer \| null` | servicio | Máximo índice de evidencia 0–100; no es probabilidad |
| `context_flags` | `string[]` | servicio | Señales contextuales de las detecciones |
| `hull_area_km2` | `number \| null` | servicio | Área del hull; **no** es área quemada |
| `rank` | `integer` | módulo | Orden por FRP descendente |
| `puntos_ids` | `string[]` | módulo | Solo en `format=json` y en el detalle |

---

## 7. `GET /api/v1/susceptibility`

Mapa agregado de riesgo. Requiere el artefacto `data/processed/susceptibility.json`.

### 7.1 Parámetros

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `level` | `province` o `canton` | `province` | Nivel de agregación |
| `region_id` | `str` | `null` | Filtrar por región o provincia |
| `format` | `str` | `geojson` | `geojson` o `json` |

### 7.2 Artefacto ausente — `200 pending`

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-11-14",
      "end": "2026-11-21"
    },
    "filters": {
      "region_id": null,
      "sensor": null,
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "module": {
      "name": "susceptibility",
      "status": "pending",
      "version": null
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "El mapa agregado aún no se generó. Mientras tanto, usa /api/v1/susceptibility/point para consultas puntuales."
    ]
  },
  "data": {
    "level": "province",
    "type": "FeatureCollection",
    "features": [],
    "model": {
      "name": "HistGradientBoostingClassifier",
      "version": null,
      "trained_at": null,
      "window_days": 7,
      "metrics": {
        "auc_roc": null,
        "average_precision": null,
        "brier": null
      }
    },
    "risk_bands": [],
    "summary": {
      "areas_total": 0,
      "areas_in_scope": 24,
      "by_risk": {
        "Bajo": 0,
        "Medio": 0,
        "Alto": 0,
        "Extremo": 0
      },
      "generated_at": null
    }
  }
}
```

### 7.3 Artefacto disponible — ejemplo ilustrativo

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-11-14",
      "end": "2026-11-21"
    },
    "filters": {
      "region_id": null,
      "sensor": null,
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "module": {
      "name": "susceptibility",
      "status": "available",
      "version": "fuegoclaro-risk-20261114T225059Z"
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "El nivel de riesgo es la categoría de una probabilidad del modelo, no una predicción determinista de incendio."
    ]
  },
  "data": {
    "level": "province",
    "type": "FeatureCollection",
    "model": {
      "name": "HistGradientBoostingClassifier",
      "version": "fuegoclaro-risk-20261114T225059Z",
      "trained_at": "2026-11-14T22:50:59Z",
      "window_days": 7,
      "metrics": {
        "auc_roc": 0.86,
        "average_precision": 0.41,
        "brier": 0.03
      }
    },
    "risk_bands": [
      {
        "level": "Bajo",
        "min_probability": 0.0,
        "max_probability_exclusive": 0.005054
      },
      {
        "level": "Medio",
        "min_probability": 0.005054,
        "max_probability_exclusive": 0.086304
      },
      {
        "level": "Alto",
        "min_probability": 0.086304,
        "max_probability_exclusive": 0.245562
      },
      {
        "level": "Extremo",
        "min_probability": 0.245562,
        "max_probability": 1.0
      }
    ],
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Polygon",
          "coordinates": [
            [
              [-79.6, -4.6],
              [-79.2, -4.6],
              [-79.2, -3.9],
              [-79.6, -3.9],
              [-79.6, -4.6]
            ]
          ]
        },
        "properties": {
          "area_id": "loja",
          "area_name": "Loja",
          "level": "province",
          "probability_max": 0.31,
          "probability_mean": 0.08,
          "risk_level": "Extremo",
          "cells_count": 142,
          "model_version": "fuegoclaro-risk-20261114T225059Z",
          "rank": 1,
          "drivers": [
            {"feature": "fire_freq_cell", "value": 0.42, "importance": 0.12},
            {"feature": "days_since_fire", "value": 61, "importance": 0.04}
          ],
          "valid_from": "2026-11-14",
          "valid_to": "2026-11-21"
        }
      }
    ],
    "summary": {
      "areas_total": 1,
      "areas_in_scope": 24,
      "by_risk": {
        "Bajo": 0,
        "Medio": 0,
        "Alto": 0,
        "Extremo": 1
      },
      "generated_at": "2026-11-14T23:10:00Z"
    }
  }
}
```

### 7.4 Umbrales reales

Los umbrales vienen de `data/processed/ml/risk_thresholds.json` y **dependen del horizonte** `window_days`.

| `window_days` | `q50` | `q85` | `q95` |
|---|---|---|---|
| 0 | 0.000558 | 0.008590 | 0.047356 |
| 1 | 0.001682 | 0.022829 | 0.095513 |
| 2 | 0.002264 | 0.035863 | 0.132143 |
| 3 | 0.002824 | 0.046968 | 0.149573 |
| 4 | 0.004364 | 0.056497 | 0.189197 |
| 5 | 0.005118 | 0.065980 | 0.199014 |
| 6 | 0.005420 | 0.081650 | 0.221950 |
| 7 | 0.005054 | 0.086304 | 0.245562 |

Regla del modelo (`risk_levels()`):

- `Bajo`: `probability <= q50`
- `Medio`: `q50 < probability <= q85`
- `Alto`: `q85 < probability <= q95`
- `Extremo`: `probability > q95`

> **Importante:** una probabilidad de `0.10` es `Alto` para `window_days=7` aunque parezca baja en términos absolutos. La tasa base de positivos es ≈1.1 %; los umbrales son percentiles de validación, no bandas fijas. El frontend **no debe** traducir probabilidad a color con cortes 0.3/0.6/0.8.

---

## 8. `GET /api/v1/susceptibility/point`

Predicción puntual en vivo con `FireRiskPredictor`.

### 8.1 Parámetros

| Parámetro | Tipo | Obligatorio | Descripción |
|---|---|---|---|
| `lat` | `float` | Sí | Latitud WGS84, dentro del BBox |
| `lon` | `float` | Sí | Longitud WGS84, dentro del BBox |
| `date` | `YYYY-MM-DD` | Sí | Fecha local |
| `window_days` | `int` | No (7) | Horizonte `0..7` |

BBox: `(-92.5, -5.5, -74.5, 2.0)`.

### 8.2 Ejemplo de respuesta

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-11-20",
      "end": "2026-11-27"
    },
    "filters": {
      "region_id": null,
      "sensor": null,
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "module": {
      "name": "susceptibility",
      "status": "available",
      "version": "fuegoclaro-risk-20261114T225059Z"
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "Predicción puntual basada en la celda 0.1° más cercana con historial."
    ]
  },
  "data": {
    "cell_id": "-45_-795",
    "latitude": -4.4161,
    "longitude": -79.54454,
    "cell_center": {
      "lat": -4.45,
      "lon": -79.55
    },
    "distance_to_cell_km": 3.9,
    "date": "2026-11-20",
    "window_days": 7,
    "probability": 0.1874,
    "risk_level": "Alto",
    "thresholds": {
      "q50": 0.005054118298677622,
      "q85": 0.08630444544229905,
      "q95": 0.2455621301775148,
      "method": "percentiles de validación (p50/p85/p95)"
    },
    "model_version": "fuegoclaro-risk-20261114T225059Z",
    "calibration": {
      "method": "isotonic"
    },
    "data_completeness": 0.94,
    "top_factors": [
      {
        "feature": "fire_freq_cell",
        "value": 0.42,
        "importance": 0.1206
      },
      {
        "feature": "days_since_fire",
        "value": 61,
        "importance": 0.0439
      },
      {
        "feature": "wx_relative_humidity_2m_mean_d0",
        "value": 48.2,
        "importance": 0.0237
      },
      {
        "feature": "wx_precipitation_sum_lag1",
        "value": 0.0,
        "importance": 0.0146
      },
      {
        "feature": "viirs_count_lag7",
        "value": 3,
        "importance": 0.014
      }
    ],
    "warnings": [
      "La fecha consultada no está en el histórico exacto: se usó el último estado disponible hasta esa fecha y el calendario de la fecha solicitada."
    ],
    "disclaimer": "Probabilidad basada en datos históricos NASA FIRMS, clima, DEM y NDVI. Una detección de foco de calor no equivale a un incendio confirmado."
  }
}
```

### 8.3 Campos

| Campo | Tipo | Descripción |
|---|---|---|
| `cell_id` | `string` | Celda 0.1° usada |
| `cell_center` | `{lat, lon}` | Centro de la celda |
| `distance_to_cell_km` | `number` | Distancia al centro |
| `probability` | `number` | Probabilidad calibrada `0..1` |
| `risk_level` | `string` | `Bajo`, `Medio`, `Alto`, `Extremo` |
| `thresholds` | `object` | `q50`, `q85`, `q95`, `method` |
| `model_version` | `string \| null` | Versión del bundle |
| `calibration` | `object \| null` | Método de calibración |
| `data_completeness` | `number` | Fracción de features no nulas |
| `top_factors` | `object[]` | `feature`, `value`, `importance` |
| `warnings` | `string[]` | Avisos de la inferencia |
| `disclaimer` | `string` | Advertencia científica |

---

## 9. `GET /api/v1/analytics/summary`

Resumen compuesto: detecciones + eventos + riesgo.

### 9.1 Parámetros

`start_date`, `end_date`, `region_id`, `sensor`, `confidence`, `daynight`, `min_frp`, `bbox`.

### 9.2 Respuesta con susceptibilidad pendiente

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31"
    },
    "filters": {
      "region_id": "all",
      "sensor": "all",
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null,
      "severity": null,
      "province_ids": []
    },
    "modules": {
      "detections": "available",
      "clustering": "available",
      "susceptibility": "pending"
    },
    "attribution": "NASA FIRMS",
    "notes": [
      "La distribución de riesgo queda vacía porque el mapa agregado aún no está disponible."
    ]
  },
  "data": {
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31",
      "days": 31
    },
    "kpis": {
      "detections_total": 1240,
      "active_days": 18,
      "fire_events_total": 12,
      "critical_events": 3,
      "extreme_risk_areas": 0,
      "provinces_affected": 6,
      "frp_total_mw": 842.3
    },
    "by_sensor": [
      {
        "sensor": "VIIRS",
        "count": 980,
        "share": 0.7903,
        "frp_sum_mw": 601.4,
        "frp_mean_mw": 0.61
      },
      {
        "sensor": "MODIS",
        "count": 260,
        "share": 0.2097,
        "frp_sum_mw": 240.9,
        "frp_mean_mw": 0.93
      }
    ],
    "by_region": [
      {"region_id": "sierra", "region": "Sierra", "count": 620, "share": 0.5},
      {"region_id": "amazonia", "region": "Amazonía", "count": 410, "share": 0.3306},
      {"region_id": "costa", "region": "Costa", "count": 210, "share": 0.1694}
    ],
    "by_severity": {
      "alerta_roja": 3,
      "alerta_media": 5,
      "quema_menor": 4
    },
    "risk_distribution": {
      "Bajo": 0,
      "Medio": 0,
      "Alto": 0,
      "Extremo": 0
    },
    "timeseries": [
      {
        "period": "2026-08-01",
        "sensor": "MODIS",
        "count": 12,
        "frp_sum": 18.4,
        "frp_mean": 1.53,
        "active_days": 1
      },
      {
        "period": "2026-08-01",
        "sensor": "VIIRS",
        "count": 41,
        "frp_sum": 22.1,
        "frp_mean": 0.54,
        "active_days": 1
      }
    ],
    "alerts": [
      {
        "id_evento": "EVT-0001",
        "centro": [-4.06, -79.16],
        "inicio": "2026-08-15",
        "nivel_alerta": "alerta_roja",
        "province_names": ["Loja"],
        "frp_total": 342.5,
        "puntos_count": 27
      }
    ],
    "top_provinces": [
      {"province_id": "loja", "province": "Loja", "count": 210, "share": 0.1694},
      {"province_id": "azuay", "province": "Azuay", "count": 180, "share": 0.1452}
    ],
    "notes": [
      "El resumen es exploratorio; no confirma incendios ni cuantifica superficie quemada."
    ]
  }
}
```

### 9.3 Campos

| Campo | Tipo | Descripción |
|---|---|---|
| `kpis.detections_total` | `integer` | Detecciones del periodo |
| `kpis.active_days` | `integer` | Días con detecciones |
| `kpis.fire_events_total` | `integer` | Eventos agrupados |
| `kpis.critical_events` | `integer` | Eventos `alerta_roja` |
| `kpis.extreme_risk_areas` | `integer` | Áreas en riesgo extremo (`0` si el mapa está `pending`) |
| `kpis.provinces_affected` | `integer` | Provincias con detecciones |
| `kpis.frp_total_mw` | `number \| null` | FRP total si es calculable |
| `by_sensor` | `object[]` | Desglose MODIS/VIIRS |
| `by_region` | `object[]` | Desglose por región natural |
| `by_severity` | `object` | Conteo por `nivel_alerta` |
| `risk_distribution` | `object` | Conteo por `risk_level` (`Bajo`, `Medio`, `Alto`, `Extremo`) |
| `timeseries` | `object[]` | Series por periodo y sensor |
| `alerts` | `object[]` | Eventos `alerta_roja` para el feed |
| `top_provinces` | `object[]` | Provincias con más detecciones |

---

## 10. Anexo A — Detecciones existentes (sin cambios)

```json
{
  "meta": {
    "data_mode": "real",
    "dataset_version": "fuegoclaro-20261113T003529Z",
    "generated_at": "2026-11-13T00:35:29Z",
    "period": {
      "start": "2026-08-01",
      "end": "2026-08-31"
    },
    "filters": {
      "region_id": "all",
      "sensor": "all",
      "confidence": [],
      "daynight": null,
      "min_frp": null,
      "bbox": null
    },
    "attribution": "NASA FIRMS",
    "notes": []
  },
  "pagination": {
    "total": 1240,
    "limit": 5000,
    "offset": 0,
    "returned": 1,
    "truncated": true
  },
  "data": [
    {
      "id": "7f3c2a1b9d8e4f60",
      "sensor": "VIIRS",
      "satellite": "NOAA-20",
      "instrument": "VIIRS",
      "source_product": "VIIRS_NOAA20_NRT",
      "latitude": -4.0123,
      "longitude": -79.2345,
      "acq_date": "2026-08-15",
      "acq_time": "0310",
      "acq_date_local": "2026-08-14",
      "acq_time_local": "22100",
      "acquired_at_utc": "2026-08-15T03:10:00Z",
      "daynight": "N",
      "confidence_level": "high",
      "confidence_raw": "h",
      "confidence_score": null,
      "frp": 42.7,
      "brightness": 331.2,
      "bright_t31": null,
      "bright_ti5": 295.4,
      "scan": 0.375,
      "track": 0.375,
      "version": "2.0NRT",
      "type": "0",
      "province": "Loja",
      "province_id": "loja",
      "region": "Sierra",
      "region_id": "sierra",
      "provenance_id": "fuegoclaro-20261113T003529Z"
    }
  ]
}
```

---

## 11. Mapeo módulo → API

| Campo API | Origen real | Transformación |
|---|---|---|
| `id_evento` | `detect_fire_events().id_evento` | directa |
| `frp_total` | `.frp_total` | directa |
| `frp_max` | `.frp_max` | directa |
| `frp_medio` | `.frp_medio` | directa |
| `puntos_count` | `.puntos_count` | directa |
| `geometria` | `.geometria` | GeoJSON Polygon |
| `centro` | `.centro` | `[lat, lon]` |
| `inicio` / `fin` | `.inicio` / `.fin` | fecha `YYYY-MM-DD` |
| `nivel_alerta` | `.nivel_alerta` | directa |
| `motivo_regla` | `.motivo_regla` | directa |
| `provincias` | `.provincias` | IDs |
| `sensores` | `.sensores` | directa |
| `province_names` | `utils.geo.regions_payload()` | servicio |
| `confidence_by_level` | `puntos_ids` + `confidence_level` | servicio |
| `evidence_score_max` | `fire_evidence.annotate_fire_evidence()` | servicio |
| `hull_area_km2` | `geometria` | servicio (shapely) |
| `probability` | `predict().probability` | directa |
| `risk_level` | `.risk_level` | directa (`Bajo`, `Medio`, `Alto`, `Extremo`) |
| `thresholds` | `.thresholds` | directa |
| `top_factors` | `.top_factors` | directa |
| `warnings` | `.warnings` | directa |

Funciones reales:

```python
detect_fire_events(df_detections, *, eps_km=2.0, eps_days=2, min_points=1) -> list[dict]
FireRiskPredictor().predict(latitude, longitude, when, window_days=7) -> dict
risk_levels(probabilities, thresholds) -> np.ndarray  # Bajo/Medio/Alto/Extremo
```

Regla de capas: el controlador **no** llama a estas funciones; solo al servicio.

---

## 12. Reglas científicas para el frontend

1. Mostrar siempre: **detección ≠ incendio confirmado ≠ superficie quemada**.
2. No sumar MODIS y VIIRS como si fueran el mismo sensor.
3. La razón VIIRS/MODIS es una razón de **conteos**, no de área.
4. `hull_area_km2` es el hull del cluster, no área quemada.
5. `evidence_score_max` es un índice transparente 0–100, no una probabilidad.
6. `risk_level` es la categoría de una probabilidad calibrada; no es certeza.
7. Los colores de riesgo se asignan por `risk_level` (`Bajo`, `Medio`, `Alto`, `Extremo`), **no** por cortes fijos de probabilidad.
8. `null` significa “no disponible”; no reemplazarlo por `0` en la UI.
9. Si `module.status == "pending"`, mostrar un estado vacío explícito.
10. La ausencia de detecciones no implica ausencia de fuego.
11. `inicio`/`fin` son fechas; la UI no debe inventar una hora.
12. `canton` es `null` hasta que exista asignación cantonal.

---

## 13. Mejoras abiertas para revisión

- [ ] Añadir `canton_id` y `canton` cuando exista la capa cantonal.
- [ ] Añadir `event_timeline` con evolución diaria del cluster.
- [ ] Añadir `severity_rank` explícito para ordenar el feed.
- [ ] Añadir `confidence_by_sensor` dentro del evento.
- [ ] Añadir `model.explainability` con SHAP agregado.
- [ ] Añadir `format=csv` para exportar eventos.
- [ ] Añadir `ETag`/`Cache-Control` a los artefactos.
- [ ] Añadir `module.last_run_at` y `module.records`.
- [ ] Generar tipos TypeScript desde OpenAPI.
- [ ] Evaluar `format=geojson` como default definitivo o cambiar a `dashboard`.

---

## 14. Criterios de aceptación

- [ ] Todos los JSON de este documento son válidos.
- [ ] `/fire-events` responde `format=geojson` por defecto con `FeatureCollection`.
- [ ] `/fire-events?format=dashboard` cumple `FireDashboard` de `src/types/fire.ts`.
- [ ] `/fire-events?format=json` devuelve lista paginada.
- [ ] `/fire-events/{id}` devuelve `404` con envelope cuando no existe.
- [ ] `/susceptibility` devuelve `200 pending` sin artefacto.
- [ ] `/susceptibility/point` devuelve `probability` y `risk_level` en español.
- [ ] `/analytics/summary` refleja módulos `pending` sin fallar.
- [ ] Los endpoints legacy no cambian.
- [ ] El frontend renderiza estados vacíos sin errores.
- [ ] El contrato se comparte con Juanito, Erickoso, ñoquito, Marcelo y Mateogod.
