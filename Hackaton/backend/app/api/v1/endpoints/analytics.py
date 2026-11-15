"""Controlador del resumen analítico compuesto."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import common_filters, response_meta
from app.domain.models import FilterSpec
from app.services import analytics_service
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["analítica"])


@router.get("/analytics/summary")
def analytics_summary(spec: FilterSpec = Depends(common_filters)) -> dict:
    data, modules = analytics_service.summary(spec)
    meta = response_meta(get_store(), spec, notes=data.notes)
    meta["modules"] = modules
    return json_safe({"meta": meta, "data": data.model_dump()})
