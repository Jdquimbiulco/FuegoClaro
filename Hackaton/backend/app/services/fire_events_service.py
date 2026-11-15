"""Orquestación de eventos de fuego sin dependencia de FastAPI."""

from __future__ import annotations

from collections import Counter, OrderedDict
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

_CACHE_SIZE = 2
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
        frame = apply_filters(get_store().df, spec)
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


def _enrich(event: dict, evidence_by_id: dict, catalog: dict[str, dict]) -> FireEventDTO:
    members = [evidence_by_id[str(value)] for value in event.get("puntos_ids", [])
               if str(value) in evidence_by_id]
    counts = {level: 0 for level in ("low", "nominal", "high", "unknown")}
    for member in members:
        level = str(member.get("confidence_level")).lower()
        if level in counts:
            counts[level] += 1
    dominant = max(counts, key=lambda level: (counts[level], level)) if sum(counts.values()) else None
    scores = [member["evidence_score"] for member in members if pd.notna(member.get("evidence_score"))]
    score = int(max(scores)) if scores else None
    flags = sorted({str(member["context_flag"]) for member in members
                    if pd.notna(member.get("context_flag")) and str(member["context_flag"]) != "none"})

    province_ids = [value for value in event.get("provincias", []) if value and value != "<NA>"]
    provinces = [catalog[value] for value in province_ids if value in catalog]
    first = provinces[0] if provinces else None
    center = tuple(float(value) for value in event["centro"])
    cantons = Counter(str(member["canton"]) for member in members if pd.notna(member.get("canton")))
    canton = min(cantons, key=lambda name: (-cantons[name], name)) if cantons else None
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


def _enrich_page(events: list[dict]) -> list[FireEventDTO]:
    if not events:
        return []
    # Índice pequeño: solo miembros visibles y columnas del enriquecimiento.
    evidence = get_store().evidence_df
    ids = {str(value) for event in events for value in event["puntos_ids"]}
    columns = [name for name in ("id", "confidence_level", "evidence_score", "context_flag", "canton") if name in evidence]
    frame = evidence.loc[evidence["id"].astype(str).isin(ids), columns].copy()
    frame["_event_point_id"] = frame["id"].astype(str)
    frame = frame.drop_duplicates("_event_point_id").set_index("_event_point_id")
    indexed = {row[0]: dict(zip(frame.columns, row[1:])) for row in frame.itertuples(name=None)}
    catalog = _province_catalog()
    return [_enrich(event, indexed, catalog) for event in events]


def _events_for(spec: FilterSpec) -> list[FireEventDTO]:
    return _enrich_page(_raw_events_for(spec, geometry_mode="hull"))


def list_events(
    spec: FilterSpec,
    *,
    severity: str | None = None,
    province_ids: list[str] | None = None,
    limit: int = 500,
    offset: int = 0,
) -> tuple[list[FireEventDTO], int]:
    selected = _select_raw_events(spec, severity, province_ids, geometry_mode="hull")
    return _enrich_page(selected[offset : offset + limit]), len(selected)


def event_detail(event_id: str) -> FireEventDTO:
    store = get_store()
    start, end = store.default_window()
    spec = FilterSpec(start_date=start, end_date=end, region_id="all", sensor="all")
    for event in _raw_events_for(spec, geometry_mode="hull"):
        if event["id_evento"] == event_id:
            return _enrich_page([event])[0]
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
    events = _enrich_page(raw_events[:event_limit])

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
