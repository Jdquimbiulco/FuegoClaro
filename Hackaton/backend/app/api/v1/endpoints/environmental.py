"""Capas SNAP y alertas ambientales calculadas bajo demanda."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import common_filters, response_meta
from app.domain.models import FilterSpec
from app.services import environmental_alerts_service, protected_areas_service
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["impacto ambiental"])


@router.get("/protected-areas")
def protected_areas() -> dict:
    payload = protected_areas_service.geojson()
    return json_safe(
        {
            "meta": {
                "module": protected_areas_service.status(),
                "notes": payload.pop("notes", []),
            },
            "data": payload,
        }
    )


@router.get("/environmental-alerts")
def environmental_alerts(
    spec: FilterSpec = Depends(common_filters),
    window_days: int = Query(7, ge=0, le=7),
) -> dict:
    payload = environmental_alerts_service.list_alerts(spec, window_days=window_days)
    meta = response_meta(get_store(), spec, notes=payload["notes"])
    meta["filters"]["window_days"] = window_days
    meta["module"] = {"protected_areas": protected_areas_service.status(), "persistence": "none"}
    return json_safe({"meta": meta, "data": payload})
