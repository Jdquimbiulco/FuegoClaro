"""Comparador MODIS vs VIIRS."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import common_filters, response_meta
from app.domain.comparison import build_comparison
from app.domain.models import FilterSpec
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["comparación"])


@router.get("/comparison")
def comparison(
    spec: FilterSpec = Depends(common_filters),
    granularity: str = Query("month", pattern="^(day|week|month)$"),
) -> dict:
    store = get_store()
    data = build_comparison(store.df, spec, granularity=granularity)
    return json_safe({"meta": response_meta(store, spec, notes=data.get("notes")), "data": data})
