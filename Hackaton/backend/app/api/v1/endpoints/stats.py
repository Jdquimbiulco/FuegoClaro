"""Indicadores del dashboard y series temporales."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import common_filters, response_meta
from app.domain.aggregation import build_summary, build_timeseries
from app.domain.models import FilterSpec
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["estadísticas"])


@router.get("/stats/summary")
def summary(spec: FilterSpec = Depends(common_filters)) -> dict:
    store = get_store()
    data = build_summary(store.df, spec)
    return json_safe({"meta": response_meta(store, spec, notes=data.get("notes")), "data": data})


@router.get("/stats/timeseries")
def timeseries(
    spec: FilterSpec = Depends(common_filters),
    granularity: str = Query("month", pattern="^(day|week|month)$"),
) -> dict:
    store = get_store()
    data = build_timeseries(store.df, spec, granularity=granularity)
    return json_safe({"meta": response_meta(store, spec, notes=data.get("notes")), "data": data})
