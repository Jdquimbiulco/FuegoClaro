"""Alertas ambientales efímeras derivadas de riesgo, SNAP y eventos observados."""

from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Any

from app.domain.models import FilterSpec
from app.services import fire_events_service, protected_areas_service, susceptibility_service
from app.services.data_store import apply_filters, get_store

_OBSERVED_CACHE: OrderedDict[tuple, list[dict[str, Any]]] = OrderedDict()
_CACHE_SIZE = 16


def _alert_id(kind: str, subject: str, area_id: str) -> str:
    return f"{kind}:{subject}:{area_id}"


def _predictive_alerts(window_days: int) -> list[dict[str, Any]]:
    risk = susceptibility_service.get_map(level="cell", window_days=window_days)
    alerts: list[dict[str, Any]] = []
    for feature in risk.features:
        props = feature.get("properties", {})
        level = props.get("risk_level")
        # Regla acordada: Galápagos se visualiza, pero no genera alertas automáticas
        # de prioridad alta por la posible señal volcánica.
        if level not in {"Alto", "Extremo"} or props.get("region_id") == "galapagos":
            continue
        for area in protected_areas_service.intersecting_areas(feature["geometry"]):
            area_props = area["properties"]
            alerts.append(
                {
                    "id": _alert_id("predictive", str(props.get("area_id")), str(area_props["area_id"])),
                    "type": "predictive_environmental_risk",
                    "priority": "critical" if level == "Extremo" else "high",
                    "title": "Riesgo ambiental predictivo",
                    "coordinates": [props.get("latitude"), props.get("longitude")],
                    "risk": {"cell_id": props.get("area_id"), "probability": props.get("probability"), "level": level, "window_days": window_days, "prediction_date": props.get("prediction_date")},
                    "protected_area": {"id": area_props["area_id"], "name": area_props["name"], "category": area_props["category"], "subsystem": area_props["subsystem"]},
                    "disclaimer": "Intersección de una celda de riesgo (~11 km) con SNAP; no confirma un incendio ni afectación dentro de toda el área.",
                }
            )
    return alerts


def _observed_cache_key(spec: FilterSpec) -> tuple:
    path = get_store().meta.path
    mtime = Path(path).stat().st_mtime if path and Path(path).exists() else None
    return (mtime, spec.start_date, spec.end_date, spec.region_id, spec.sensor, tuple(spec.confidence), spec.daynight, spec.min_frp, spec.bbox)


def _build_observed_alerts(spec: FilterSpec) -> list[dict[str, Any]]:
    events, _ = fire_events_service.list_events(spec, severity="alerta_roja", limit=5000)
    evidence = apply_filters(get_store().evidence_df, spec)
    if evidence.empty:
        return []
    points = evidence.set_index(evidence["id"].astype(str), drop=False)
    alerts: list[dict[str, Any]] = []
    for event in events:
        for point_id in event.puntos_ids:
            if point_id not in points.index:
                continue
            point = points.loc[point_id]
            # El cruce se hace con cada punto real, no con el hull del evento.
            geometry = {"type": "Point", "coordinates": [float(point["longitude"]), float(point["latitude"])]}
            for area in protected_areas_service.intersecting_areas(geometry):
                area_props = area["properties"]
                identifier = _alert_id("observed", event.id_evento, str(area_props["area_id"]))
                if any(item["id"] == identifier for item in alerts):
                    continue
                alerts.append(
                    {
                        "id": identifier,
                        "type": "observed_environmental_event",
                        "priority": "critical",
                        "title": "Evento térmico crítico en área protegida",
                        "coordinates": [float(point["latitude"]), float(point["longitude"])],
                        "event": {"id": event.id_evento, "level": event.nivel_alerta, "start": event.inicio, "end": event.fin, "frp_total": event.frp_total},
                        "protected_area": {"id": area_props["area_id"], "name": area_props["name"], "category": area_props["category"], "subsystem": area_props["subsystem"]},
                        "disclaimer": "Una detección térmica dentro de SNAP requiere verificación en campo; no confirma incendio ni superficie afectada.",
                    }
                )
    return alerts


def _observed_alerts(spec: FilterSpec) -> list[dict[str, Any]]:
    """Caché únicamente en memoria; no crea historial ni estado de alertas."""
    key = _observed_cache_key(spec)
    cached = _OBSERVED_CACHE.get(key)
    if cached is not None:
        _OBSERVED_CACHE.move_to_end(key)
        return cached
    alerts = _build_observed_alerts(spec)
    _OBSERVED_CACHE[key] = alerts
    _OBSERVED_CACHE.move_to_end(key)
    while len(_OBSERVED_CACHE) > _CACHE_SIZE:
        _OBSERVED_CACHE.popitem(last=False)
    return alerts


def list_alerts(spec: FilterSpec, *, window_days: int = 7) -> dict[str, Any]:
    predictive = _predictive_alerts(window_days)
    observed = _observed_alerts(spec)
    alerts = sorted(predictive + observed, key=lambda item: (0 if item["priority"] == "critical" else 1, item["id"]))
    return {
        "alerts": alerts,
        "summary": {
            "total": len(alerts),
            "predictive": len(predictive),
            "observed": len(observed),
            "critical": sum(item["priority"] == "critical" for item in alerts),
        },
        "notes": [
            "Las alertas se calculan en cada consulta y no se persisten.",
            "Galápagos se excluye de alertas automáticas prioritarias por posible actividad volcánica.",
        ],
    }
