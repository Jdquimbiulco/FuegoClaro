# FuegoClaro — Plan de implementación Persona 1 (Gabo)

**Estado:** aprobado en decisiones, listo para implementación. **No se ha escrito código ni ejecutado pruebas de servicios.**
**Alcance:** exponer por HTTP los módulos reales que ya llegaron en el pull (clustering de eventos y riesgo ML), separando **servicios** de **controlador**.
**Base de código:** `Hackaton/backend`
**Contrato frontend-backend:** `json_exmp.md`

> **Regla de oro del testeo:** el testeo de los servicios **lo ejecuta Gabo manualmente**. El asistente no corre estos comandos, no levanta el servidor y no valida resultados. La sección 9 explica el procedimiento exacto para que él lo haga.

---

## 0. Cómo leer este plan

1. Secciones 1–2: qué llegó en el pull y cómo se separan las capas.
2. Secciones 3–4: contratos de **servicios** y mapeo de las claves reales del pull.
3. Secciones 5–7: **controladores**, compatibilidad con el frontend actual y archivos a crear.
4. Sección 8: caché, concurrencia y rendimiento.
5. Sección 9: **testeo manual** (lo ejecuta Gabo).
6. Secciones 10–15: pruebas entregables, riesgos, fase 2, definición de terminado y decisiones abiertas.

---

## 1. Qué cambió con el pull

El pull ya incorporó lógica real. Este plan **deja de asumir módulos vacíos** y pasa a integrar lo existente.

### 1.1 Backend

| Archivo | Qué aporta | Estado |
|---|---|---|
| `backend/app/domain/fire_events.py` | `detect_fire_events(df, *, eps_km, eps_days, min_points, flare_radius_km, flare_sources) -> list[dict]`; ST-DBSCAN, exclusión de mecheros, convex hull, motor de reglas | Real y probado |
| `backend/app/domain/fire_evidence.py` | Índice de evidencia 0–100 por detección y `context_flag` | Real |
| `backend/app/ml/inference.py` | `FireRiskPredictor(...).predict(lat, lon, fecha, window_days)` | Real |
| `backend/app/ml/training.py` | `risk_levels()` con umbrales p50/p85/p95 | Real |
| `backend/app/ml/grid.py` | Celdas 0.1°, provincia/región por celda, vecinos | Real |
| `Hackaton/scripts/predict_fire_risk.py` | CLI de inferencia puntual y por lote | Real |
| `Hackaton/scripts/train_fire_risk_model.py` | Entrenamiento y artefactos | Real |
| `Hackaton/scripts/build_fire_risk_dataset.py` | Dataset supervisado | Real |
| `backend/app/services/data_store.py` | `get_store()`, `apply_filters()`, `evidence_df` | Real |
| `backend/app/core/errors.py` | `FuegoClaroError`, `NotFoundError`, `bad_request()` | Real |
| `backend/app/main.py` | Handlers que ya devuelven `{"error": {"code","message","details"}}` | Real |

### 1.2 Artefactos ML presentes en `data/processed/ml/`

```
cells_static.parquet
fire_risk_dataset.parquet
fire_risk_dataset.meta.json
risk_model.joblib
risk_feature_columns.json
risk_feature_importance.csv
risk_model_metrics.json
risk_thresholds.json
```

No existe `data/processed/susceptibility.json`. El mapa agregado sigue siendo un artefacto a generar (sección 12).

### 1.3 Frontend ya existente

| Archivo | Contrato actual |
|---|---|
| `frontend/src/types/fire.ts` | `FireEvent` con claves en **español** (`id_evento`, `centro`, `frp_total`, `puntos_count`, `nivel_alerta`, `provincias`, `province_names`, `canton`, `nocturnas`, `sensores`) y `FireDashboard` |
| `frontend/src/hooks/useFireDashboard.ts` | `GET /api/v1/fire-events` → `{ meta, data: FireDashboard }`; si recibe `404`, usa demo |
| `frontend/src/pages/FiresPage.tsx` | Consume `FireDashboard` y muestra `confirmed_critical`/`extreme_risk_cantons` como “Sin datos” cuando son `null` |
| `frontend/FIRE_EVENTS_API.md` | Documenta los parámetros `start_date`, `end_date`, `region_id`, `sensor`, `confidence`, `province_ids`, `granularity` |

**Consecuencia:** el contrato de eventos debe hablar el vocabulario de `src/types/fire.ts`. No se renombra a inglés.

---

## 2. Separación de capas: dominio, servicios y controlador

### 2.1 Regla de dependencias

```
controlador (api/v1/endpoints)  ->  servicio (services)  ->  dominio / ML / data_store
        |                               |
   valida HTTP                    orquesta y transforma
   devuelve DTO                   no conoce FastAPI
```

| Capa | Carpeta | Puede importar | **No puede** importar |
|---|---|---|---|
| Dominio | `app/domain/`, `app/ml/` | numpy, pandas, shapely, sklearn | `fastapi`, `app.services`, `app.api` |
| Servicio | `app/services/` | dominio, ML, `data_store`, `core.config`, `core.errors` | `fastapi`, `app.api`, `Request`, `HTTPException` |
| Controlador | `app/api/v1/endpoints/` | `fastapi`, `app.api.deps`, `app.api.v1.schemas`, `app.services` | `pandas`, `app.ml`, `app.domain.fire_events`, `shapely` |

Esta regla se verifica con una prueba de arquitectura (sección 10.3). Si un controlador necesita `pandas`, la lógica está en el lugar equivocado.

### 2.2 Qué hace cada capa, en concreto

**Dominio (ya existe, no se toca):**
- Agrupa detecciones, calcula geometrías, clasifica alertas.
- Entrena y predice probabilidad de riesgo.
- No sabe que existe HTTP ni qué forma tiene la respuesta.

**Servicio (nuevo):**
- Pide detecciones filtradas a `DataStore`.
- Llama a `detect_fire_events()` y a `FireRiskPredictor.predict()`.
- Enriquece con nombres de provincia/región, confianza y evidencia.
- Normaliza claves, convierte fechas, ordena, pagina.
- Decide el estado del módulo (`pending`, `available`, `error`).
- Cachea resultados y el predictor.
- Devuelve **DTOs Pydantic**, nunca `dict` suelto.

**Controlador (nuevo):**
- Declara la ruta, los `Query` params y los códigos de respuesta.
- Llama a **una** función del servicio.
- Serializa el DTO (`model_dump()`).
- Traduce excepciones de servicio a `FuegoClaroError` con su `status_code`.
- No calcula nada.

### 2.3 Diagrama

```text
GET /api/v1/fire-events?format=dashboard
        |
        v
[controlador] fire_events.py
        |  valida query params con common_filters()
        v
[servicio] fire_events_service.dashboard(spec, granularity, province_ids)
        |                 |
        |                 +--> data_store.apply_filters()
        |                 +--> domain.fire_events.detect_fire_events()
        |                 +--> domain.aggregation.build_timeseries()
        |                 +--> domain.fire_evidence (enriquecimiento opcional)
        v
   FireDashboardDTO  ->  JSON
```

```text
GET /api/v1/susceptibility/point?lat=-4.41&lon=-79.54&date=2026-11-20
        |
        v
[controlador] susceptibility.py
        |
        v
[servicio] susceptibility_service.predict_point()
        |
        +--> model_registry.get_fire_risk_predictor()
        |         +--> FireRiskPredictor (singleton, carga diferida)
        v
   PointRiskDTO  ->  JSON
```

---

## 3. Contratos de los servicios

### 3.1 `app/services/module_registry.py`

Responsabilidad: saber si un módulo está disponible sin cargarlo dos veces y sin romper el arranque.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ModuleInfo:
    name: str
    status: str          # "pending" | "available" | "error"
    version: str | None
    artifact: str | None
    detail: str | None = None


def predictor_artifacts_present() -> bool: ...
def get_fire_risk_predictor() -> FireRiskPredictor: ...
def predictor_info() -> ModuleInfo: ...
```

Reglas:
- `get_fire_risk_predictor()` es **singleton perezoso** con `threading.Lock`, porque `FireRiskPredictor.__init__` carga `risk_model.joblib` y `cells_static.parquet`.
- **No se instancia al arrancar la app.** El `lifespan` actual solo carga `DataStore`; se mantiene así.
- Si faltan artefactos, lanza `ModuleNotReadyError` (subclase de `FuegoClaroError`, `503`).
- Si el `.joblib` está corrupto, lanza `ModuleContractError` (`503`) y no deja el proceso en estado inconsistente.
- `predictor_info()` informa `version` desde `bundle["version"]` sin predecir.

### 3.2 `app/services/fire_events_service.py`

```python
def module_info() -> ModuleInfo: ...

def list_events(
    spec: FilterSpec,
    *,
    severity: str | None = None,
    province_ids: list[str] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[FireEventDTO], int]: ...

def event_detail(event_id: str) -> FireEventDTO: ...

def dashboard(
    spec: FilterSpec,
    *,
    granularity: str = "month",
    province_ids: list[str] | None = None,
) -> FireDashboardDTO: ...

def summary(
    spec: FilterSpec,
    *,
    severity: str | None = None,
) -> FireEventsSummaryDTO: ...
```

Implementación:

1. `df = apply_filters(get_store().evidence_df, spec)`.
   Se usa `evidence_df` solo si el enriquecimiento está activo; si cuesta demasiado, `get_store().df` y el enriquecimiento se calcula por evento sobre sus miembros.
2. `events = detect_fire_events(df)` con los parámetros por defecto del dominio (`eps_km=2.0`, `eps_days=2`, `min_points=1`). No se inventan parámetros nuevos en el controlador.
3. Se mapean claves (sección 4.1) y se enriquece.
4. Se filtra por `severity` y `province_ids` **después** del clustering.
5. Se ordena por severidad (`alerta_roja` → `alerta_media` → `quema_menor`) y luego por `frp_total` descendente.
6. Se aplica `limit`/`offset` al final y se devuelve el total **sin paginar**.
7. Cache in-process (sección 8) con clave `(dataset_mtime, spec, severity, province_ids)`.

`dashboard()` añade, sobre la misma lista de eventos:
- `summary`: detecciones filtradas, eventos, críticos, `frp_total`, `confirmed_critical = null`, `extreme_risk_cantons = null`.
- `by_province`: conteo de eventos por provincia.
- `series`: `build_timeseries(store.df, spec, granularity)`.
- `seasonality`: conteo por mes usando los mismos filtros **excepto fechas** (histórico completo).
- `history_period`: `min/max` de `acq_date_local` del dataset filtrado sin fechas.
- `notes`: aviso de que un evento no es superficie quemada y que `null` ≠ `0`.

`event_detail()` busca en `list_events()` sin paginar; si no existe y el módulo está `available`, lanza `NotFoundError`.

**Nunca devuelve `404` por módulo ausente.** `detect_fire_events` está en el repo, por lo que el módulo de eventos queda `available` en la práctica; el estado `pending` queda como salvaguarda si el dominio se desactiva por configuración.

### 3.3 `app/services/susceptibility_service.py`

Dos responsabilidades distintas, deliberadamente separadas:

```python
def module_info() -> ModuleInfo: ...

# Mapa agregado (artefacto precalculado)
def get_map(
    *,
    level: str = "province",          # "province" | "canton"
    region_id: str | None = None,
) -> SusceptibilityMapDTO: ...

# Predicción puntual en vivo (modelo real del pull)
def predict_point(
    *,
    latitude: float,
    longitude: float,
    when: str,
    window_days: int = 7,
) -> PointRiskDTO: ...
```

`get_map()`:
- Lee `settings.processed_dir / "susceptibility.json"`.
- Si no existe → `status="pending"`, `FeatureCollection` vacía y `notes` con el comando que lo genera.
- Si existe pero no cumple el contrato → `ModuleContractError` (`503`).
- Cache por `mtime`.

`predict_point()`:
- Valida `-92.5 <= lon <= -74.5` y `-5.5 <= lat <= 2.0` (BBox del proyecto). Fuera de rango → `ValidationError` del servicio → `422`.
- Valida `window_days` en `0..7`; el predictor ya lo recorta, pero el servicio lo declara.
- Llama `get_fire_risk_predictor().predict(...)`.
- Conserva `risk_level` **en español** (`Bajo`, `Medio`, `Alto`, `Extremo`), `thresholds`, `top_factors`, `warnings`, `disclaimer`.
- **No** agrega `risk_level_id`: el contrato usa una sola etiqueta, la del modelo. El frontend mapea colores desde `risk_level`.

**No se inventan polígonos provinciales a partir de un punto.** La predicción puntual es puntual; el mapa agregado requiere el artefacto de la sección 12.

### 3.4 `app/services/analytics_service.py`

```python
def summary(spec: FilterSpec) -> AnalyticsSummaryDTO: ...
```

Composición explícita, sin duplicar lógica:

| Bloque | Origen |
|---|---|
| `detections_total`, `active_days`, `provinces_affected`, `frp_total_mw` | `build_summary(store.df, spec)` |
| `by_sensor`, `by_region`, `by_province` | `build_summary(...)` |
| `timeseries` | `build_timeseries(store.df, spec, granularity="day")` |
| `fire_events_total`, `critical_events`, `by_severity`, `alerts` | `fire_events_service.list_events()` |
| `risk_distribution`, `extreme_risk_areas` | `susceptibility_service.get_map()` (claves en español: `Bajo`, `Medio`, `Alto`, `Extremo`) |
| `meta.modules` | `module_info()` de cada servicio |

Reglas:
- Nunca lanza por módulo `pending`: lo refleja en `meta.modules` y deja conteos en `0`.
- `frp_total_mw` es `null` si no hay FRP válido, no `0`.
- `alerts` = hasta 10 eventos `alerta_roja` ordenados por FRP desc.
- `notes` incluye la advertencia científica y el estado de módulos pendientes.

### 3.5 Errores de servicio

Añadir a `app/core/errors.py` (sin romper lo existente):

```python
class ModuleNotReadyError(FuegoClaroError):
    def __init__(self, module: str, detail: str | None = None):
        super().__init__(
            "MODULE_UNAVAILABLE",
            f"El módulo '{module}' no está disponible.",
            status_code=503,
            details={"module": module, "status": "pending", "detail": detail},
        )

class ModuleContractError(FuegoClaroError):
    def __init__(self, module: str, detail: str):
        super().__init__(
            "CONTRACT_ERROR",
            f"El módulo '{module}' devolvió datos que no cumplen el contrato.",
            status_code=503,
            details={"module": module, "status": "error", "detail": detail},
        )
```

Los handlers de `main.py` ya serializan `FuegoClaroError` al envelope `{"error": ...}`. **No se toca `main.py`.**

---

## 4. DTOs y mapeo real

### 4.1 Eventos: claves reales de `detect_fire_events()` → DTO

Se conserva el vocabulario del frontend (`src/types/fire.ts`). No se renombra a inglés.

| Clave del pull | Clave del DTO | Tipo | Origen |
|---|---|---|---|
| `id_evento` | `id_evento` | `str` | módulo |
| `frp_total` | `frp_total` | `float` | módulo |
| `frp_max` | `frp_max` | `float` | módulo |
| `frp_medio` | `frp_medio` | `float` | módulo |
| `puntos_count` | `puntos_count` | `int` | módulo |
| `geometria` | `geometria` | `dict` (Polygon) | módulo |
| `centro` | `centro` | `[float, float]` (lat, lon) | módulo |
| `inicio` | `inicio` | `str` (`YYYY-MM-DD`) | módulo |
| `fin` | `fin` | `str` (`YYYY-MM-DD`) | módulo |
| `dias` | `dias` | `list[str]` | módulo |
| `diurnas` | `diurnas` | `int` | módulo |
| `nocturnas` | `nocturnas` | `int` | módulo |
| `sensores` | `sensores` | `list[str]` | módulo |
| `provincias` | `provincias` | `list[str]` | módulo |
| `puntos_ids` | `puntos_ids` | `list[str]` | módulo |
| `contraste_medio_k` | `contraste_medio_k` | `float` | módulo |
| `nivel_alerta` | `nivel_alerta` | `str` | módulo |
| `nivel_alerta_label` | `nivel_alerta_label` | `str` | módulo |
| `motivo_regla` | `motivo_regla` | `str` | módulo |
| `rank` | `rank` | `int` | módulo |
| — | `province_names` | `list[str]` | **servicio**: `regions_payload()` |
| — | `region_id` / `region` | `str` | **servicio**: primera provincia del evento |
| — | `canton` | `str \| null` | **servicio**: `null` (sin asignación cantonal) |
| — | `confidence_by_level` | `dict[str, int]` | **servicio**: miembros por `confidence_level` |
| — | `confidence_dominant` | `str` | **servicio**: argmax de lo anterior |
| — | `evidence_score_max` | `int \| null` | **servicio**: máximo de `evidence_score` de los miembros |
| — | `context_flags` | `list[str]` | **servicio**: `context_flag` únicos de los miembros |
| — | `hull_area_km2` | `float \| null` | **servicio**: área aproximada del hull, **no** área quemada |

> Nada de esto se inventa: los campos derivados salen de las detecciones que el propio evento lista en `puntos_ids`. Si el enriquecimiento falla, el campo va `null`, no `0`.

**Corrección importante frente al plan anterior:** `inicio` y `fin` son **fechas**, no datetimes con hora. El módulo no devuelve hora de inicio/fin. El contrato debe reflejarlo así.

**Corrección importante:** el módulo **no** devuelve `severity`, `evidence_score`, `confidence_dominant`, `hull_area_km2` ni `context_flags` por evento. Todo eso lo calcula el servicio (tabla anterior).

### 4.2 Riesgo puntual: `FireRiskPredictor.predict()` → DTO

| Clave del pull | Clave del DTO | Nota |
|---|---|---|
| `cell_id` | `cell_id` | celda 0.1° |
| `latitude`, `longitude` | igual | punto consultado |
| `cell_center` | `cell_center` | `{lat, lon}` |
| `distance_to_cell_km` | `distance_to_cell_km` | si el punto no cae en celda terrestre |
| `date` | `date` | `YYYY-MM-DD` |
| `window_days` | `window_days` | `0..7` |
| `probability` | `probability` | `0..1` |
| `risk_level` | `risk_level` | `Bajo`, `Medio`, `Alto`, `Extremo` |
| `thresholds` | `thresholds` | `q50`, `q85`, `q95`, `method` |
| `model_version` | `model_version` | del bundle |
| `calibration` | `calibration` | tal cual |
| `data_completeness` | `data_completeness` | fracción de features no nulas |
| `top_factors` | `top_factors` | `feature`, `value`, `importance` |
| `warnings` | `warnings` | incluye aviso de Galápagos/fecha fuera de histórico |
| `disclaimer` | `disclaimer` | se conserva textual |

### 4.3 `FireDashboard` (feed del frontend)

Sin cambios de forma respecto a `src/types/fire.ts`:

```json
{
  "period": {"start": "2026-08-01", "end": "2026-08-31"},
  "summary": {
    "detections": 1240,
    "events": 12,
    "critical_events": 3,
    "confirmed_critical": null,
    "extreme_risk_cantons": null,
    "frp_total": 842.3
  },
  "events": [],
  "by_province": [],
  "series": [],
  "seasonality": [],
  "history_period": {"start": "2022-01-01", "end": "2026-11-12"},
  "notes": []
}
```

`confirmed_critical` y `extreme_risk_cantons` son `null` porque no existe fuente de confirmación ni agregación cantonal. Un `0` significaría “medido y sin casos”, y eso no es cierto.

---

## 5. Controladores HTTP

### 5.1 `GET /api/v1/fire-events`

Un solo endpoint, tres representaciones:

| `format` | Respuesta | Uso |
|---|---|---|
| `geojson` (default) | `{meta, pagination, data: FeatureCollection}` | capa del mapa |
| `dashboard` | `{meta, data: FireDashboard}` | feed actual de `useFireDashboard` |
| `json` | `{meta, pagination, data: [FireEventDTO]}` | tablas y depuración |

Parámetros:

| Parámetro | Tipo | Default | Descripción |
|---|---|---|---|
| `start_date`, `end_date` | fecha | ventana por defecto | vía `common_filters` |
| `region_id`, `sensor`, `confidence`, `daynight`, `min_frp` | — | — | vía `common_filters` |
| `severity` | `str` | `null` | `alerta_roja`, `alerta_media`, `quema_menor` |
| `province_ids` | `str` | `null` | IDs separados por coma |
| `granularity` | `str` | `month` | `day`, `week`, `month` (solo `dashboard`) |
| `format` | `str` | `geojson` | `geojson`, `dashboard`, `json` |
| `limit` | `int` | `500` | máx. 5000 |
| `offset` | `int` | `0` | — |

Respuestas:
- `200` con datos (el módulo de clustering ya es real).
- `422` por parámetros inválidos (handler existente).
- `503` si `detect_fire_events` falla por un artefacto corrupto (se captura como `ModuleContractError`).
- `404` **solo** en `/fire-events/{event_id}` cuando el módulo está disponible y el ID no existe.

> `severity` usa los IDs reales del módulo (`alerta_roja`...), no `critical/moderate/low`. El `json_exmp.md` debe alinearse con esto.

### 5.2 `GET /api/v1/fire-events/{event_id}`

- `200` con `FireEventDTO` (formato JSON plano, sin GeoJSON) + `meta`.
- `404` si no existe.

### 5.3 `GET /api/v1/susceptibility`

- Mapa agregado (artefacto).
- Parámetros: `level` (`province`|`canton`), `region_id`, `format` (`geojson`|`json`).
- `200` + `module.status="pending"` si el artefacto no existe.
- `200` + `FeatureCollection` si existe.
- `503` si el artefacto es inválido.

### 5.4 `GET /api/v1/susceptibility/point`

- Predicción puntual en vivo.
- Parámetros obligatorios: `lat`, `lon`, `date`.
- Opcional: `window_days` (`0..7`, default `7`).
- `200` con `PointRiskDTO`.
- `422` fuera del BBox de Ecuador o fecha inválida.
- `503` si faltan los artefactos ML (`ModuleNotReadyError`).

### 5.5 `GET /api/v1/analytics/summary`

- Parámetros: los de `common_filters`.
- `200` siempre (aunque clustering o susceptibilidad estén `pending`).
- `data.kpis`, `by_sensor`, `by_region`, `by_severity`, `risk_distribution`, `timeseries`, `alerts`, `top_provinces`, `notes`.
- `meta.modules`: `detections`, `clustering`, `susceptibility`.

### 5.6 Registro

`backend/app/api/v1/router.py`:

```python
from app.api.v1.endpoints import (
    analytics,
    anomalies,
    calendar,
    comparison,
    detections,
    export,
    fire_events,
    health,
    insights,
    meta,
    stats,
    susceptibility,
)

router.include_router(fire_events.router)
router.include_router(susceptibility.router)
router.include_router(analytics.router)
```

### 5.7 Regla de controlador delgado

Ejemplo correcto:

```python
@router.get("/fire-events")
def fire_events(
    spec: FilterSpec = Depends(common_filters),
    severity: str | None = Query(None, pattern="^(alerta_roja|alerta_media|quema_menor)$"),
    province_ids: str | None = Query(None),
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    format: str = Query("geojson", pattern="^(geojson|dashboard|json)$"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    provinces = [item for item in (province_ids or "").split(",") if item]
    if format == "dashboard":
        dto = fire_events_service.dashboard(spec, granularity=granularity, province_ids=provinces)
        return json_safe({"meta": response_meta(get_store(), spec, notes=dto.notes), "data": dto.model_dump()})
    events, total = fire_events_service.list_events(
        spec, severity=severity, province_ids=provinces, limit=limit, offset=offset
    )
    ...
```

Nada de `detect_fire_events`, `apply_filters` ni `pandas` en este archivo.

---

## 6. Compatibilidad con el frontend actual

| Elemento | Cambio necesario | Motivo |
|---|---|---|
| `useFireDashboard.ts` | añadir `format: 'dashboard'` al `withQuery` | el default del endpoint es `geojson` para el mapa |
| `FiresPage.tsx` | sin cambios | sigue recibiendo `FireDashboard` |
| `types/fire.ts` | sin cambios obligatorios | se conservan las claves |
| `types/fire.ts` (opcional) | añadir `province_names`, `frp_max`, `region_id` | campos nuevos ya presentes en la respuesta |
| Mapa de eventos | nuevo componente | consumirá `format=geojson` |
| `FIRE_EVENTS_API.md` | actualizar la ruta con `format=dashboard` | documentación |

**Decisión confirmada:** `format=geojson` es el default y `useFireDashboard` pedirá `format=dashboard`. No se cambia la forma de `FireDashboard`.

---

## 7. Archivos a crear y modificar

```text
Hackaton/backend/app/
├── api/v1/
│   ├── endpoints/
│   │   ├── fire_events.py            [NUEVO controlador]
│   │   ├── susceptibility.py         [NUEVO controlador]
│   │   ├── analytics.py              [NUEVO controlador]
│   │   └── router.py                 [MODIFICAR]
│   ├── schemas/
│   │   ├── common.py                 [NUEVO]
│   │   ├── fire_events.py            [NUEVO]
│   │   ├── susceptibility.py         [NUEVO]
│   │   └── analytics.py              [NUEVO]
├── core/
│   └── errors.py                     [MODIFICAR: +2 excepciones]
└── services/
    ├── module_registry.py            [NUEVO]
    ├── fire_events_service.py        [NUEVO]
    ├── susceptibility_service.py     [NUEVO]
    └── analytics_service.py          [NUEVO]

Hackaton/tests/backend/
├── test_services_fire_events.py      [NUEVO]
├── test_services_susceptibility.py   [NUEVO]
├── test_services_analytics.py        [NUEVO]
├── test_controllers_new.py           [NUEVO]
└── test_architecture_layers.py       [NUEVO]
```

Se actualiza además `json_exmp.md`.

**No se modifica** ningún endpoint existente (`/detections`, `/stats/*`, `/calendar`, `/comparison`, `/anomalies`, `/insights`, `/meta`, `/export`).

---

## 8. Caché, concurrencia y rendimiento

| Elemento | Estrategia |
|---|---|
| Dataset de detecciones | ya cacheado por `DataStore` con `mtime` |
| Predictor ML | singleton perezoso con `threading.Lock`; se carga una vez por proceso |
| Eventos | `lru_cache(maxsize=16)` sobre `(mtime, spec, severity, province_ids)`; el clustering de 116 730 detecciones puede tardar segundos |
| Artefacto de susceptibilidad | cache por `mtime` |
| Analytics | cache corto (30 s) o reutilización del cache de eventos |

Notas:
- `detect_fire_events` sobre el dataset completo es costoso (≈116 730 filas, búsqueda por rejilla + DBSCAN). La primera llamada de un filtro nuevo puede tardar varios segundos. **Medir en la prueba manual 9.3 y decidir si se precalcula.**
- `predict_point` lee `fire_risk_dataset.parquet` filtrado por celda/fecha. Primera llamada: segundos; siguientes: caché del sistema operativo.
- El modelo **no** se carga si nadie llama a `/susceptibility/point`.
- El proceso es síncrono; si el clustering bloquea demasiado, se puede mover a `run_in_threadpool`. Se decide después de medir.

---

## 9. Testeo manual (lo ejecuta Gabo)

> **El asistente no ejecutará nada de esta sección.** No levantará `uvicorn`, no hará peticiones, no correrá `pytest` ni interpretará resultados. Gabo ejecuta y reporta.

### 9.1 Preparación

Si `backend\.venv` no existe (en este workspace no está creado), créalo una sola vez con Python 3.13:

```powershell
cd C:\Users\gmlop\Desktop\ESPE\Hackaton\FuegoClaro\Hackaton\backend
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt
```

Luego verifica dependencias y artefactos:

```powershell
cd C:\Users\gmlop\Desktop\ESPE\Hackaton\FuegoClaro\Hackaton
backend\.venv\Scripts\python.exe -c "import fastapi, pandas, sklearn, joblib; print('deps ok')"
Test-Path data\processed\ml\risk_model.joblib
Test-Path data\processed\ml\fire_risk_dataset.parquet
```

Esperado: `deps ok`, y dos `True`.

> Si `pyarrow` está bloqueado por Application Control en este equipo (ver `AGENTS.md`), ejecutar las pruebas 9.2 y 9.4 dentro de Docker.

### 9.2 Probar los servicios sin HTTP

**A. Cluster de eventos (dominio puro, sin servicio todavía):**

```powershell
@'
import sys
sys.path.insert(0, "backend")
from app.services.data_store import get_store
from app.domain.fire_events import detect_fire_events

df = get_store().df
print("detecciones:", len(df))
events = detect_fire_events(df.head(5000))
print("eventos:", len(events))
if events:
    e = events[0]
    print({k: e[k] for k in ("id_evento", "frp_total", "puntos_count", "nivel_alerta", "inicio", "fin", "provincias")})
'@ | backend\.venv\Scripts\python.exe -
```

Comprobar:
- `eventos > 0` con las primeras 5 000 filas.
- `nivel_alerta` ∈ `{alerta_roja, alerta_media, quema_menor}`.
- `inicio`/`fin` son fechas `YYYY-MM-DD`.
- `provincias` contiene IDs (no nombres).

**B. Predictor ML puntual:**

```powershell
@'
import sys, json
sys.path.insert(0, "backend")
from app.ml.inference import FireRiskPredictor

predictor = FireRiskPredictor()
result = predictor.predict(-4.4161, -79.54454, "2026-11-20", window_days=7)
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
'@ | backend\.venv\Scripts\python.exe -
```

Comprobar:
- `0.0 <= probability <= 1.0`.
- `risk_level` ∈ `{Bajo, Medio, Alto, Extremo}`.
- `thresholds` tiene `q50`, `q85`, `q95`.
- `top_factors` no vacío.
- `warnings` puede estar vacío; si la fecha no es histórica, debe advertirlo.
- `disclaimer` presente.

**C. Servicios ya implementados** (cuando existan):

```powershell
@'
import sys, json
sys.path.insert(0, "backend")
from app.domain.models import FilterSpec
from app.services.data_store import get_store
from app.services import fire_events_service, analytics_service

store = get_store()
start, end = store.default_window(days=30)
spec = FilterSpec(start_date=start, end_date=end, region_id="all", sensor="all")

events, total = fire_events_service.list_events(spec, limit=5)
print("total eventos:", total)
print(json.dumps(events[0].model_dump() if events else {}, ensure_ascii=False, indent=2))

dash = fire_events_service.dashboard(spec, granularity="month")
print("dashboard keys:", sorted(dash.model_dump().keys()))
print("summary:", dash.summary.model_dump())

analytics = analytics_service.summary(spec)
print("kpis:", analytics.kpis.model_dump())
print("modulos:", analytics.modules)
'@ | backend\.venv\Scripts\python.exe -
```

Comprobar:
- `total eventos` es coherente con el feed.
- `dashboard.summary.events == total` (mismo filtro).
- `confirmed_critical` y `extreme_risk_cantons` son `None`.
- `analytics.modules["clustering"] == "available"`.
- `analytics.modules["susceptibility"] == "pending"` mientras no exista el artefacto.

**D. Servicio de susceptibilidad puntual:**

```powershell
@'
import sys, json
sys.path.insert(0, "backend")
from app.services import susceptibility_service

print(susceptibility_service.module_info())
print(json.dumps(susceptibility_service.predict_point(
    latitude=-4.4161, longitude=-79.54454, when="2026-11-20", window_days=7
).model_dump(), ensure_ascii=False, indent=2, default=str))
'@ | backend\.venv\Scripts\python.exe -
```

Comprobar:
- `module_info().status == "available"` si existen los artefactos.
- `risk_level` ∈ `{Bajo, Medio, Alto, Extremo}`.
- `probability` y `risk_level` son coherentes con `thresholds`.

### 9.3 Probar los controladores con `uvicorn`

Terminal 1:

```powershell
cd C:\Users\gmlop\Desktop\ESPE\Hackaton\FuegoClaro\Hackaton\backend
.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Terminal 2:

```powershell
# GeoJSON (mapa)
curl.exe -s "http://localhost:8000/api/v1/fire-events?start_date=2026-08-01&end_date=2026-08-31" | ConvertFrom-Json | ConvertTo-Json -Depth 4

# Dashboard (feed)
curl.exe -s "http://localhost:8000/api/v1/fire-events?start_date=2026-08-01&end_date=2026-08-31&format=dashboard" | ConvertFrom-Json | Select-Object -ExpandProperty data | Select-Object -ExpandProperty summary

# JSON plano
curl.exe -s "http://localhost:8000/api/v1/fire-events?limit=2&format=json" | ConvertFrom-Json | Select-Object -ExpandProperty pagination

# Detalle
curl.exe -s "http://localhost:8000/api/v1/fire-events/EVT-0001" | ConvertFrom-Json

# Susceptibilidad puntual
curl.exe -s "http://localhost:8000/api/v1/susceptibility/point?lat=-4.4161&lon=-79.54454&date=2026-11-20&window_days=7" | ConvertFrom-Json

# Susceptibilidad agregada (debe ser 200 pending)
curl.exe -s "http://localhost:8000/api/v1/susceptibility" | ConvertFrom-Json | Select-Object -ExpandProperty data -ExpandProperty features

# Analytics
curl.exe -s "http://localhost:8000/api/v1/analytics/summary?start_date=2026-08-01&end_date=2026-08-31" | ConvertFrom-Json | Select-Object -ExpandProperty meta -ExpandProperty modules

# OpenAPI
curl.exe -s "http://localhost:8000/openapi.json" | ConvertFrom-Json | Select-Object -ExpandProperty paths | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name
```

Comprobar:
- `openapi.json` lista `/api/v1/fire-events`, `/api/v1/fire-events/{event_id}`, `/api/v1/susceptibility`, `/api/v1/susceptibility/point`, `/api/v1/analytics/summary`.
- `format=dashboard` devuelve `data.summary.events` numérico.
- `format=geojson` devuelve `data.type == "FeatureCollection"`.
- `/susceptibility` devuelve `meta.module.status == "pending"` y `data.features == []`.
- `/susceptibility/point` devuelve `probability` y `risk_level` en español.
- Un `lat` fuera de rango devuelve `422` con `error.code == "VALIDATION_ERROR"`.
- Un `event_id` inexistente devuelve `404` con `error.code == "NOT_FOUND"`.

**Medir tiempos** (importante para decidir caché):

```powershell
Measure-Command { curl.exe -s "http://localhost:8000/api/v1/fire-events?start_date=2026-01-01&end_date=2026-11-12&format=dashboard" | Out-Null }
Measure-Command { curl.exe -s "http://localhost:8000/api/v1/susceptibility/point?lat=-4.4161&lon=-79.54454&date=2026-11-20" | Out-Null }
```

Reportar: primer request (frío) y segundo request (caliente).

### 9.4 Probar con Docker

```powershell
cd C:\Users\gmlop\Desktop\ESPE\Hackaton\FuegoClaro\Hackaton
docker compose up -d --build
docker compose ps
curl.exe -s "http://localhost:8000/api/v1/health"
curl.exe -s "http://localhost:8000/api/v1/fire-events?format=dashboard" | ConvertFrom-Json | Select-Object -ExpandProperty data -ExpandProperty summary
curl.exe -s "http://localhost:8000/api/v1/susceptibility/point?lat=-4.4161&lon=-79.54454&date=2026-11-20" | ConvertFrom-Json | Select-Object probability, risk_level, model_version
docker compose logs --tail=50 backend
```

Comprobar:
- `ps` muestra `backend` como `healthy`.
- Los logs no muestran `Traceback`.
- El contenedor ve `data/processed/ml` (volumen `./data:/app/data`).
- Si el modelo no se cargó al arrancar, no debe haber error en el log de inicio; solo se carga al primer `/susceptibility/point`.

### 9.5 Checklist de aceptación manual

- [ ] `detect_fire_events` devuelve eventos con claves documentadas.
- [ ] `FireRiskPredictor.predict` devuelve probabilidad y nivel.
- [ ] `fire_events_service.dashboard` cumple `FireDashboard`.
- [ ] `fire_events_service.list_events` pagina y filtra por severidad/provincia.
- [ ] `susceptibility_service.get_map` devuelve `pending` sin artefacto.
- [ ] `susceptibility_service.predict_point` devuelve `risk_level` en español.
- [ ] `analytics_service.summary` compone sin duplicar `/stats/summary`.
- [ ] Los 5 endpoints responden con el envelope esperado.
- [ ] Los errores usan `{"error": {"code","message","details"}}`.
- [ ] `openapi.json` incluye las rutas nuevas.
- [ ] Los endpoints legacy siguen respondiendo igual.
- [ ] Tiempos medidos y anotados para decidir caché/precálculo.

### 9.6 Qué **no** probar todavía

- Mapa provincial de susceptibilidad: no existe artefacto (fase 2, sección 12).
- Confirmaciones de incendios: no hay fuente.
- Agregación cantonal: no hay asignación cantonal.
- Precisión científica del modelo: fuera del alcance de esta fase; no se valida aquí.

---

## 10. Pruebas automatizadas que se entregarán (las ejecuta Gabo o CI)

> El asistente **no las ejecuta**. Se entregan escritas; su ejecución y lectura de resultados es manual o de CI.

### 10.1 Servicios

`tests/backend/test_services_fire_events.py`
- Con un `DataFrame` sintético, `list_events()` devuelve DTOs, no `dict`.
- El total no cambia al paginar.
- `severity` filtra correctamente.
- `dashboard().summary.events == total`.
- `confirmed_critical is None`.

`tests/backend/test_services_susceptibility.py`
- Sin artefacto → `get_map().status == "pending"` y `features == []`.
- `predict_point()` con artefactos presentes → `0 <= probability <= 1` y `risk_level` en `{Bajo, Medio, Alto, Extremo}`.
- Coordenada fuera del BBox → error de validación.

`tests/backend/test_services_analytics.py`
- Con clustering disponible y susceptibilidad `pending`, `modules` lo refleja.
- `frp_total_mw is None` si no hay FRP.
- No lanza excepción con dataset vacío.

### 10.2 Controladores

`tests/backend/test_controllers_new.py`
- `200` en los 5 endpoints.
- `format=geojson` → `FeatureCollection`.
- `format=dashboard` → claves de `FireDashboard`.
- `format=json` → lista.
- `404` en detalle inexistente.
- `422` en `lat` fuera de rango.
- Envelope de error correcto.

### 10.3 Arquitectura

`tests/backend/test_architecture_layers.py`
- `endpoints/fire_events.py` no contiene `import pandas`, `app.ml` ni `app.domain.fire_events`.
- `services/*.py` no contiene `import fastapi`.
- `services/*.py` no contiene `HTTPException`.

### 10.4 Comando

```powershell
cd Hackaton
backend\.venv\Scripts\python.exe -m pytest -q
```

En Docker:

```powershell
docker compose run --rm backend python -m pytest -q
```

---

## 11. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El default `geojson` rompe `useFireDashboard` | añadir `format=dashboard` en el hook (1 línea) o cambiar el default; decisión en sección 15 |
| Clustering lento en ventanas largas | caché + medir en 9.3; evaluar precálculo |
| El modelo no carga al arrancar | carga perezosa con lock; `pending`/`503`, nunca caída del proceso |
| Artefacto ML ausente en Docker | `./data:/app/data` ya montado; documentar `docker compose restart backend` tras generarlo |
| Se inventan campos por evento | tabla 4.1 marca origen; derivados van `null` si no se pueden calcular |
| `inicio`/`fin` sin hora | contrato corregido a fecha; no se fabrica una hora |
| Mapa provincial confundido con predicción puntual | endpoints separados y `notes` explícitas |
| Diferencias MODIS/VIIRS | se conservan `sensores`, `diurnas`, `nocturnas`, `confidence_by_level`; no se suman como área |
| Controlador con lógica | prueba de arquitectura 10.3 |
| Endpoints legacy rotos | no se tocan; solo se añaden routers |

---

## 12. Fase 2 opcional: mapa agregado de susceptibilidad

No bloquea esta entrega. Se implementa solo si el usuario lo aprueba después de las pruebas manuales.

1. Nuevo script `scripts/build_susceptibility_map.py`.
2. Lee `cells_static.parquet` y el dataset de features.
3. Predice por celda (en lote, no celda por celda) para una fecha y `window_days`.
4. Agrega por provincia con una regla explícita:
   - `probability_max` (peor caso),
   - `probability_mean`,
   - `cells_count`,
   - `risk_level` derivado de `probability_max` o de la mediana, **decisión documentada**.
5. Une con `data/regions/ecuador_provinces.geojson` (`load_province_features()`).
6. Escribe `data/processed/susceptibility.json` con el contrato de `/susceptibility`.
7. El endpoint lo sirve sin cambios: pasa de `pending` a `available`.

Regla científica: la capa provincial es una **agregación de probabilidades por celda**, no una predicción provincial independiente ni área quemada.

---

## 13. Definición de terminado

- [ ] `app/services/` contiene los 4 módulos y no importa `fastapi`.
- [ ] Los controladores solo orquestan y devuelven DTOs.
- [ ] `GET /fire-events` soporta `geojson`, `dashboard` y `json`.
- [ ] `GET /fire-events/{id}` devuelve `200`/`404`.
- [ ] `GET /susceptibility` devuelve `200 pending` sin artefacto.
- [ ] `GET /susceptibility/point` usa el modelo real.
- [ ] `GET /analytics/summary` compone detecciones + eventos + riesgo.
- [ ] El envelope de errores se mantiene.
- [ ] `json_exmp.md` refleja las claves reales.
- [ ] `useFireDashboard` funciona con `format=dashboard`.
- [ ] El enriquecimiento por evento se calcula en el servicio.
- [ ] `risk_level` se expone solo en español.
- [ ] Pruebas entregadas y **ejecutadas manualmente por Gabo**.
- [ ] Endpoints legacy sin cambios.
- [ ] Tiempos medidos y estrategia de caché confirmada.

---

## 14. Orden de ejecución

1. ~~Confirmar decisiones de la sección 15.~~ Resueltas.
2. `core/errors.py`: añadir `ModuleNotReadyError` y `ModuleContractError`.
3. `services/module_registry.py`.
4. `services/fire_events_service.py` + DTOs de eventos (con enriquecimiento).
5. `services/susceptibility_service.py` + DTOs de riesgo.
6. `services/analytics_service.py` + DTOs de analytics.
7. Controladores y registro en el router.
8. Añadir `format: 'dashboard'` en `useFireDashboard`.
9. Actualizar `json_exmp.md`.
10. Entregar pruebas automatizadas.
11. **Gabo ejecuta la sección 9** y reporta tiempos y resultados.
12. Ajustar caché/precálculo según lo medido.
13. Congelar contrato y compartir.

---

## 15. Decisiones resueltas

| # | Decisión | Resultado |
|---|---|---|
| 1 | Default de `/fire-events` | `geojson` por defecto; `useFireDashboard` pide `format=dashboard` |
| 2 | Enriquecimiento por evento | Se calcula **en el servicio** (`confidence_by_level`, `confidence_dominant`, `evidence_score_max`, `context_flags`, `hull_area_km2`) |
| 3 | Fechas en `/susceptibility/point` | Solo `date`; el rango se resolverá en el frontend cuando se necesite |
| 4 | Campo de nivel de riesgo | Solo `risk_level` en **español** (`Bajo`, `Medio`, `Alto`, `Extremo`); sin `risk_level_id` |

No quedan decisiones abiertas. La implementación puede comenzar por el paso 2 de la sección 14.
