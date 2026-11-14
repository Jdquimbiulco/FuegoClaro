"""Calendario mensual de detecciones."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import common_filters, response_meta
from app.domain.aggregation import build_calendar
from app.domain.models import FilterSpec
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["calendario"])


@router.get("/calendar")
def calendar(
    spec: FilterSpec = Depends(common_filters),
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$", description="Mes YYYY-MM"),
) -> dict:
    store = get_store()
    try:
        data = build_calendar(store.df, spec, month)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return json_safe({"meta": response_meta(store, spec, notes=data.get("notes")), "data": data})
