"""Controladores HTTP del módulo de eventos agrupados."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from app.api.deps import common_filters, response_meta
from app.domain.models import FilterSpec
from app.services import fire_events_service
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["eventos de fuego"])


def _province_ids(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _meta(spec: FilterSpec, *, severity: str | None = None, province_ids: list[str] | None = None, notes: list[str] | None = None) -> dict:
    payload = response_meta(get_store(), spec, notes=notes)
    payload["filters"].update({"severity": severity, "province_ids": province_ids or []})
    payload["module"] = asdict(fire_events_service.module_info())
    return payload


@router.get("/fire-events")
def fire_events(
    spec: FilterSpec = Depends(common_filters),
    severity: str | None = Query(None, pattern="^(alerta_roja|alerta_media|quema_menor)$"),
    province_ids: str | None = Query(None, description="IDs de provincia separados por coma"),
    granularity: str = Query("month", pattern="^(day|week|month)$"),
    format: str = Query("geojson", pattern="^(geojson|dashboard|json)$"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict:
    provinces = _province_ids(province_ids)
    if format == "dashboard":
        dashboard = fire_events_service.dashboard(
            spec,
            granularity=granularity,
            province_ids=provinces,
            event_limit=limit,
        )
        return json_safe({"meta": _meta(spec, province_ids=provinces, notes=dashboard.notes), "data": dashboard.model_dump()})

    events, total = fire_events_service.list_events(
        spec, severity=severity, province_ids=provinces, limit=limit, offset=offset
    )
    event_data = [event.model_dump() for event in events]
    if format == "geojson":
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": event.pop("geometria"),
                    "properties": {key: value for key, value in event.items() if key != "puntos_ids"},
                }
                for event in event_data
            ],
        }
    else:
        data = event_data
    notes = [] if total else ["No se formaron eventos con los filtros aplicados. La ausencia de detecciones no implica ausencia de fuego."]
    return json_safe(
        {
            "meta": _meta(spec, severity=severity, province_ids=provinces, notes=notes),
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "returned": len(events),
                "truncated": offset + len(events) < total,
            },
            "data": data,
        }
    )


@router.get("/fire-events/{event_id}")
def fire_event_detail(event_id: str) -> dict:
    event = fire_events_service.event_detail(event_id)
    return json_safe(
        {
            "meta": {"data_mode": get_store().mode, "module": asdict(fire_events_service.module_info())},
            "data": event.model_dump(),
        }
    )
