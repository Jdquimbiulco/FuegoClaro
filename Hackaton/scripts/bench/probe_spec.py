"""Catálogo canónico de sondas HTTP para el banco de pruebas de memoria.

Cada sonda cubre un endpoint real de la API. El catálogo es la lista cerrada de
endpoints que el comparador semántico BEFORE/AFTER debe cubrir por completo:
si se agrega un endpoint a la API hay que agregar su sonda aquí.

Convención de la URL: ``path`` es relativo a la raíz del servidor (por ejemplo
``/api/v1/detections``); el runner antepone el ``--base-url``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Ventana canónica del banco: el último año de datos procesados.
CANONICAL_START = "2025-11-13"
CANONICAL_END = "2026-11-12"

# Ventana histórica (inicio del dataset).
HISTORICAL_START = "2022-01-01"
HISTORICAL_END = "2022-12-31"


@dataclass(frozen=True)
class Probe:
    """Una sonda HTTP reproducible."""

    name: str
    path: str
    params: dict[str, Any] = field(default_factory=dict)
    method: str = "GET"
    expect: int = 200
    # Sonda cuyo cuerpo JSON se usa para resolver ids dinámicos.
    body: bool = True
    # Marca la sonda como parte de la fase concurrente de estrés.
    stress: bool = True


def _window(**extra: Any) -> dict[str, Any]:
    params = {"start_date": CANONICAL_START, "end_date": CANONICAL_END}
    params.update(extra)
    return params


PROBES: tuple[Probe, ...] = (
    # ---------------------------------------------------------------- sistema
    Probe("root", "/", body=False),
    Probe("health", "/api/v1/health"),
    Probe("meta", "/api/v1/meta"),
    Probe("regions", "/api/v1/regions"),
    Probe("regions_geojson", "/api/v1/regions/geojson"),
    Probe("provenance", "/api/v1/provenance"),
    Probe("openapi", "/openapi.json"),
    # ------------------------------------------------------------ detecciones
    Probe("detections_json", "/api/v1/detections", _window(limit=20000, format="json")),
    Probe("detections_geojson", "/api/v1/detections", _window(limit=20000, format="geojson")),
    Probe("detections_default_window", "/api/v1/detections", {"limit": 20000, "format": "json"}),
    Probe("detections_asc", "/api/v1/detections", _window(limit=20000, format="json", order="asc")),
    Probe("detections_offset", "/api/v1/detections", _window(limit=50, offset=1000)),
    Probe(
        "detections_detail",
        "/api/v1/detections/ab7c9083e7920b3b707e",
        {},
    ),
    # ------------------------------------------------------ filtros repetidos
    Probe("filter_region_sierra", "/api/v1/detections", _window(limit=20000, region_id="sierra")),
    Probe("filter_region_amazonia", "/api/v1/detections", _window(limit=20000, region_id="amazonia")),
    Probe("filter_region_galapagos", "/api/v1/detections", _window(limit=20000, region_id="galapagos")),
    Probe("filter_sensor_modis", "/api/v1/detections", _window(limit=20000, sensor="MODIS")),
    Probe("filter_sensor_viirs", "/api/v1/detections", _window(limit=20000, sensor="VIIRS")),
    Probe("filter_confidence", "/api/v1/detections", _window(limit=20000, confidence="low,nominal")),
    Probe("filter_daynight", "/api/v1/detections", _window(limit=20000, daynight="N")),
    Probe("filter_min_frp", "/api/v1/detections", _window(limit=20000, min_frp=20)),
    Probe("filter_bbox", "/api/v1/detections", _window(limit=20000, bbox="-79,-4,-78,-3")),
    Probe("filter_canton", "/api/v1/detections", _window(limit=20000, canton_id="1701")),
    # ------------------------------------------------------------------ stats
    Probe("stats_summary", "/api/v1/stats/summary", _window()),
    Probe("stats_timeseries_day", "/api/v1/stats/timeseries", _window(granularity="day")),
    Probe("stats_timeseries_month", "/api/v1/stats/timeseries", _window(granularity="month")),
    Probe("calendar_month", "/api/v1/calendar", _window(month="2026-08")),
    Probe("calendar_year", "/api/v1/calendar", _window(year=2024)),
    Probe("comparison", "/api/v1/comparison", _window(granularity="month")),
    Probe("anomalies", "/api/v1/anomalies", _window()),
    Probe("insights", "/api/v1/insights", _window()),
    Probe("export_csv", "/api/v1/export/detections.csv", _window(limit=20000), body=False),
    # ----------------------------------------------------------- eventos
    Probe("fire_events_geojson", "/api/v1/fire-events", _window(format="geojson", limit=5000)),
    Probe("fire_events_json", "/api/v1/fire-events", _window(format="json", limit=5000)),
    Probe("fire_events_dashboard", "/api/v1/fire-events", _window(format="dashboard", limit=5000)),
    Probe("fire_events_severity_roja", "/api/v1/fire-events", _window(severity="alerta_roja", format="json", limit=5000)),
    Probe("fire_events_offset", "/api/v1/fire-events", _window(format="json", limit=25, offset=100)),
    # ------------------------------------------------------ histórico
    Probe("historical_detections", "/api/v1/detections", {"start_date": HISTORICAL_START, "end_date": HISTORICAL_END, "limit": 20000}),
    Probe("historical_stats", "/api/v1/stats/summary", {"start_date": HISTORICAL_START, "end_date": HISTORICAL_END}),
    Probe("historical_fire_events", "/api/v1/fire-events", {"start_date": HISTORICAL_START, "end_date": HISTORICAL_END, "format": "json", "limit": 5000}),
    Probe("historical_insights", "/api/v1/insights", {"start_date": HISTORICAL_START, "end_date": HISTORICAL_END}),
    # -------------------------------------------------- riesgo y ambiental
    Probe("susceptibility_cell", "/api/v1/susceptibility", {"level": "cell", "window_days": 7}),
    Probe("susceptibility_province", "/api/v1/susceptibility", {"level": "province", "window_days": 7}),
    Probe("susceptibility_point", "/api/v1/susceptibility/point", {"lat": -0.5, "lon": -78.5, "date": "2026-08-15", "window_days": 7}),
    Probe("protected_areas", "/api/v1/protected-areas"),
    Probe("environmental_alerts", "/api/v1/environmental-alerts", _window()),
    Probe("environmental_alerts_h7", "/api/v1/environmental-alerts", _window(window_days=7)),
    # ------------------------------------------------------------ analítica
    Probe("analytics_summary", "/api/v1/analytics/summary", _window()),
    Probe("analytics_summary_historical", "/api/v1/analytics/summary", {"start_date": HISTORICAL_START, "end_date": HISTORICAL_END}),
)

# Sondas que se usan para resolver identificadores dinámicos en otras sondas.
DYNAMIC_SOURCES = {
    "fire_events_detail": ("fire_events_json", lambda payload: payload["data"][0]["id_evento"]),
}


def probe_names() -> list[str]:
    return [probe.name for probe in PROBES]


def by_name(name: str) -> Probe:
    for probe in PROBES:
        if probe.name == name:
            return probe
    raise KeyError(name)
