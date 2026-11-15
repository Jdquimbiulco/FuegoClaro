"""Orquestación de eventos de fuego sin dependencia de FastAPI."""

from __future__ import annotations

from collections import OrderedDict
import math
from pathlib import Path
from threading import RLock

import pandas as pd

from app.core.errors import ModuleContractError, NotFoundError
from app.domain.aggregation import build_timeseries
from app.domain.dtos import FireDashboardDTO, FireEventDTO
from app.domain.fire_events import ALERT_LEVELS, detect_fire_events
from app.domain.models import FilterSpec
from app.services.data_store import apply_filters, get_store
from app.services.module_registry import ModuleInfo
from app.utils.geo import regions_payload

_CACHE_SIZE = 16
_event_cache: OrderedDict[tuple, list[FireEventDTO]] = OrderedDict()
_raw_event_cache: OrderedDict[tuple, list[dict]] = OrderedDict()
_event_cache_lock = RLock()


def module_info() -> ModuleInfo:
    return ModuleInfo("clustering", "available", None, "app.domain.fire_events.detect_fire_events")


def _dataset_mtime() -> float | None:
    path = get_store().meta.path
    return Path(path).stat().st_mtime if path and Path(path).exists() else None


def _cache_key(spec: FilterSpec) -> tuple:
    return (
        _dataset_mtime(),
        spec.start_date,
        spec.end_date,
        spec.region_id,
        spec.canton_id,
        spec.sensor,
        tuple(spec.confidence),
        spec.daynight,
        spec.min_frp,
        spec.bbox,
    )


def _raw_events_for(spec: FilterSpec, *, geometry_mode: str) -> list[dict]:
    """Agrupa una sola vez las detecciones para consumidores concurrentes.

    El feed y las alertas ambientales se solicitan al mismo tiempo desde el
    mapa. Compartir el resultado evita ejecutar dos ST-DBSCAN idénticos.
    """
    key = (*_cache_key(spec), geometry_mode)
    with _event_cache_lock:
        cached = _raw_event_cache.get(key)
        if cached is not None:
            _raw_event_cache.move_to_end(key)
            return cached
        frame = apply_filters(get_store().evidence_df, spec)
        events = detect_fire_events(
            frame,
            eps_km=2.0,
            eps_days=2,
            min_points=1,
            geometry_mode=geometry_mode,
        )
        _raw_event_cache[key] = events
        _raw_event_cache.move_to_end(key)
        while len(_raw_event_cache) > _CACHE_SIZE:
            _raw_event_cache.popitem(last=False)
        return events


def _select_raw_events(
    spec: FilterSpec,
    severity: str | None,
    province_ids: list[str] | None,
    *,
    geometry_mode: str,
) -> list[dict]:
    if severity and severity not in ALERT_LEVELS:
        return []
    required_provinces = set(province_ids or [])
    severity_order = {"alerta_roja": 0, "alerta_media": 1, "quema_menor": 2}
    selected = [
        event for event in _raw_events_for(spec, geometry_mode=geometry_mode)
        if (severity is None or event["nivel_alerta"] == severity)
        and (not required_provinces or required_provinces.intersection(event["provincias"]))
    ]
    return sorted(selected, key=lambda event: (severity_order[event["nivel_alerta"]], -event["frp_total"]))


def _hull_area_km2(geometry: dict, latitude: float) -> float | None:
    """Área aproximada del hull en km²; explícitamente no es área quemada."""
    try:
        ring = geometry["coordinates"][0]
        if len(ring) < 4:
            return None
        factor_x = 111.32 * math.cos(math.radians(latitude))
        factor_y = 110.57
        points = [(float(lon) * factor_x, float(lat) * factor_y) for lon, lat in ring]
        double_area = sum(
            points[index][0] * points[index + 1][1] - points[index + 1][0] * points[index][1]
            for index in range(len(points) - 1)
        )
        return round(abs(double_area) / 2.0, 4)
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def _province_catalog() -> dict[str, dict]:
    return {province["id"]: province for province in regions_payload()["provinces"]}


def _event_members(evidence_by_id: pd.DataFrame, point_ids: list[str]) -> pd.DataFrame:
    """Obtiene los miembros de un evento por índice, no por escaneo completo.

    Un rango anual puede producir miles de eventos. Filtrar el DataFrame entero
    para cada uno convertía el enriquecimiento en O(eventos × detecciones) y
    mantenía bloqueadas las vistas que consumen el dashboard de eventos.
    """
    if evidence_by_id.empty or not point_ids:
        return evidence_by_id.iloc[0:0]
    return evidence_by_id.reindex(point_ids).dropna(how="all")


def _enrich(event: dict, evidence_by_id: pd.DataFrame, catalog: dict[str, dict]) -> FireEventDTO:
    members = _event_members(evidence_by_id, [str(value) for value in event.get("puntos_ids", [])])
    counts = {level: 0 for level in ("low", "nominal", "high", "unknown")}
    if not members.empty and "confidence_level" in members:
        observed = members["confidence_level"].astype(str).str.lower().value_counts()
        counts.update({level: int(observed.get(level, 0)) for level in counts})
    dominant = max(counts, key=lambda level: (counts[level], level)) if sum(counts.values()) else None
    score: int | None = None
    if not members.empty and "evidence_score" in members:
        scores = pd.to_numeric(members["evidence_score"], errors="coerce").dropna()
        score = int(scores.max()) if not scores.empty else None
    flags: list[str] = []
    if not members.empty and "context_flag" in members:
        flags = sorted({str(value) for value in members["context_flag"].dropna() if str(value) != "none"})

    province_ids = [value for value in event.get("provincias", []) if value and value != "<NA>"]
    provinces = [catalog[value] for value in province_ids if value in catalog]
    first = provinces[0] if provinces else None
    center = tuple(float(value) for value in event["centro"])
    canton = None
    if not members.empty and "canton" in members:
        values = members["canton"].dropna().astype(str)
        canton = str(values.mode().iloc[0]) if not values.empty else None
    payload = {
        **event,
        "centro": center,
        "puntos_ids": [str(value) for value in event.get("puntos_ids", [])],
        "province_names": [str(value["name"]) for value in provinces],
        "region_id": str(first["region_id"]) if first else None,
        "region": str(first["region"]) if first else None,
        "canton": canton,
        "confidence_by_level": counts,
        "confidence_dominant": dominant,
        "evidence_score_max": score,
        "context_flags": flags,
        "hull_area_km2": _hull_area_km2(event["geometria"], center[0]),
    }
    return FireEventDTO(**payload)


def _events_for(spec: FilterSpec) -> list[FireEventDTO]:
    key = _cache_key(spec)
    cached = _event_cache.get(key)
    if cached is not None:
        _event_cache.move_to_end(key)
        return cached
    try:
        frame = apply_filters(get_store().evidence_df, spec)
        raw_events = _raw_events_for(spec, geometry_mode="hull")
        catalog = _province_catalog()
        if "id" in frame:
            evidence_by_id = frame.copy()
            evidence_by_id["_event_point_id"] = evidence_by_id["id"].astype(str)
            # Los identificadores FIRMS son únicos. La deduplicación defensiva
            # evita que una fuente defectuosa vuelva ambigua la indexación.
            evidence_by_id = evidence_by_id.drop_duplicates("_event_point_id").set_index("_event_point_id", drop=False)
        else:
            evidence_by_id = frame.iloc[0:0]
        events = [_enrich(event, evidence_by_id, catalog) for event in raw_events]
    except Exception as exc:
        raise ModuleContractError("clustering", str(exc)) from exc
    _event_cache[key] = events
    _event_cache.move_to_end(key)
    while len(_event_cache) > _CACHE_SIZE:
        _event_cache.popitem(last=False)
    return events


def _filtered_events(
    spec: FilterSpec,
    severity: str | None,
    province_ids: list[str] | None,
) -> list[FireEventDTO]:
    if severity and severity not in ALERT_LEVELS:
        return []
    required_provinces = set(province_ids or [])
    severity_order = {"alerta_roja": 0, "alerta_media": 1, "quema_menor": 2}
    selected = [
        event for event in _events_for(spec)
        if (severity is None or event.nivel_alerta == severity)
        and (not required_provinces or required_provinces.intersection(event.provincias))
    ]
    return sorted(selected, key=lambda event: (severity_order[event.nivel_alerta], -event.frp_total))


def list_events(
    spec: FilterSpec,
    *,
    severity: str | None = None,
    province_ids: list[str] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[FireEventDTO], int]:
    selected = _filtered_events(spec, severity, province_ids)
    return selected[offset : offset + limit], len(selected)


def event_detail(event_id: str) -> FireEventDTO:
    store = get_store()
    start, end = store.default_window()
    spec = FilterSpec(start_date=start, end_date=end, region_id="all", sensor="all")
    for event in _events_for(spec):
        if event.id_evento == event_id:
            return event
    raise NotFoundError(f"Evento no encontrado: {event_id}")


def dashboard(
    spec: FilterSpec,
    *,
    granularity: str = "month",
    province_ids: list[str] | None = None,
    event_limit: int = 500,
) -> FireDashboardDTO:
    raw_events = _select_raw_events(spec, None, province_ids, geometry_mode="bbox")
    store = get_store()
    filtered_detections = apply_filters(store.df, spec)
    by_province: dict[str, int] = {}
    catalog = _province_catalog()
    for event in raw_events:
        for province_id in event["provincias"]:
            by_province[province_id] = by_province.get(province_id, 0) + 1
    province_rows = [
        {"id": province_id, "name": str(catalog.get(province_id, {}).get("name", province_id)), "count": count}
        for province_id, count in by_province.items()
    ]
    province_rows.sort(key=lambda item: (-int(item["count"]), str(item["name"])))

    # Sólo las tarjetas visibles requieren enriquecimiento (cantón, evidencia,
    # área aproximada). El total se conserva en el resumen sin serializar miles
    # de geometrías ni recorrer el DataFrame para cada evento.
    evidence = apply_filters(store.evidence_df, spec)
    if "id" in evidence:
        evidence_by_id = evidence.copy()
        evidence_by_id["_event_point_id"] = evidence_by_id["id"].astype(str)
        evidence_by_id = evidence_by_id.drop_duplicates("_event_point_id").set_index("_event_point_id", drop=False)
    else:
        evidence_by_id = evidence.iloc[0:0]
    events = [_enrich(event, evidence_by_id, catalog) for event in raw_events[:event_limit]]

    historic_start, historic_end = store.date_bounds()
    historical_spec = FilterSpec(
        start_date=historic_start or spec.start_date,
        end_date=historic_end or spec.end_date,
        region_id=spec.region_id,
        canton_id=spec.canton_id,
        sensor=spec.sensor,
        confidence=spec.confidence,
        daynight=spec.daynight,
        min_frp=spec.min_frp,
        bbox=spec.bbox,
    )
    history = apply_filters(store.df, historical_spec)
    seasonality: list[dict[str, str | int]] = []
    if not history.empty:
        periods = pd.to_datetime(history["acq_date_local"], errors="coerce").dt.strftime("%Y-%m")
        seasonality = [
            {"period": str(period), "count": int(count)}
            for period, count in periods.value_counts().sort_index().items()
            if pd.notna(period)
        ]
    series = build_timeseries(store.df, spec, granularity=granularity)["series"]
    frp = pd.to_numeric(filtered_detections.get("frp"), errors="coerce").dropna() if "frp" in filtered_detections else pd.Series(dtype=float)
    return FireDashboardDTO(
        period={"start": spec.start_date, "end": spec.end_date},
        summary={
            "detections": int(len(filtered_detections)),
            "events": len(raw_events),
            "critical_events": sum(event["nivel_alerta"] == "alerta_roja" for event in raw_events),
            "confirmed_critical": None,
            "extreme_risk_cantons": None,
            "frp_total": round(float(frp.sum()), 2) if not frp.empty else None,
        },
        events=events,
        by_province=province_rows,
        series=series,
        seasonality=seasonality,
        history_period={"start": historic_start, "end": historic_end},
        notes=[
            "El feed es exploratorio; los eventos agrupan detecciones y no confirman incendios ni cuantifican superficie quemada.",
            "confirmed_critical y extreme_risk_cantons no están disponibles porque no existe una fuente de confirmación ni agregación cantonal.",
        ],
    )
