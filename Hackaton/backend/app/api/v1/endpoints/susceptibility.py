"""Controladores HTTP del riesgo de incendio."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta

from fastapi import APIRouter, Query

from app.api.deps import response_meta
from app.core.config import get_settings
from app.domain.models import FilterSpec
from app.services import susceptibility_service
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["susceptibilidad"])


def _map_meta(region_id: str | None, notes: list[str]) -> dict:
    store = get_store()
    start, end = store.default_window()
    spec = FilterSpec(start_date=start, end_date=end, region_id=region_id or "all", sensor="all")
    payload = response_meta(store, spec, notes=notes)
    map_path = get_settings().processed_dir / "susceptibility.json"
    payload["module"] = {
        "name": "susceptibility",
        "status": "available" if map_path.exists() else "pending",
        "version": None,
        "artifact": str(map_path) if map_path.exists() else None,
    }
    return payload


@router.get("/susceptibility")
def susceptibility_map(
    level: str = Query("province", pattern="^(province|canton)$"),
    region_id: str | None = Query(None),
    format: str = Query("geojson", pattern="^(geojson|json)$"),
) -> dict:
    data = susceptibility_service.get_map(level=level, region_id=region_id)
    payload = data.model_dump()
    if format == "json":
        payload.pop("type", None)
    return json_safe({"meta": _map_meta(region_id, data.notes), "data": payload})


@router.get("/susceptibility/point")
def susceptibility_point(
    lat: float = Query(..., ge=-5.5, le=2.0),
    lon: float = Query(..., ge=-92.5, le=-74.5),
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    window_days: int = Query(7, ge=0, le=7),
) -> dict:
    point = susceptibility_service.predict_point(latitude=lat, longitude=lon, when=date, window_days=window_days)
    store = get_store()
    try:
        start = date
        end = (date_from_iso(date) + timedelta(days=window_days)).isoformat()
    except ValueError:
        start = end = date
    spec = FilterSpec(start_date=start, end_date=end, region_id="all", sensor="all")
    meta = response_meta(store, spec, notes=["Predicción puntual basada en la celda 0.1° más cercana con historial."])
    meta["module"] = asdict(susceptibility_service.module_info())
    return json_safe({"meta": meta, "data": point.model_dump()})


def date_from_iso(value: str) -> date:
    return date.fromisoformat(value)
