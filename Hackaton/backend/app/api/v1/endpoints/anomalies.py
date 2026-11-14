"""Radar de anomalías estadísticas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.api.deps import common_filters, response_meta
from app.domain.anomalies import detect_anomalies
from app.domain.models import FilterSpec
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["anomalías"])


@router.get("/anomalies")
def anomalies(
    spec: FilterSpec = Depends(common_filters),
    threshold: float = Query(2.5, ge=1.5, le=6.0, description="Umbral de |z-score|"),
    window_days: int = Query(7, ge=0, le=15, description="Ventana de días comparables alrededor de la fecha"),
    min_observed: int = Query(3, ge=1, le=100, description="Mínimo de detecciones observadas para reportar"),
    fdr_alpha: float = Query(0.05, gt=0, le=0.2, description="Nivel de control FDR (Benjamini-Hochberg)"),
    max_results: int = Query(40, ge=1, le=200),
) -> dict:
    store = get_store()
    data = detect_anomalies(
        store.df,
        spec,
        threshold=threshold,
        window_days=window_days,
        min_observed=min_observed,
        fdr_alpha=fdr_alpha,
        max_results=max_results,
    )
    return json_safe({"meta": response_meta(store, spec, notes=data.get("notes")), "data": data})
