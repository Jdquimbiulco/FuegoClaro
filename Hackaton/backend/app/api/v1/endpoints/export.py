"""Exportación CSV de detecciones filtradas."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from app.api.deps import common_filters
from app.api.v1.endpoints.detections import DETECTION_COLUMNS
from app.domain.models import FilterSpec
from app.services.data_store import apply_filters, get_store

router = APIRouter(tags=["exportación"])


@router.get("/export/detections.csv")
def export_detections(
    spec: FilterSpec = Depends(common_filters),
    limit: int = Query(50000, ge=1, le=200000),
) -> Response:
    store = get_store()
    filtered = apply_filters(store.df, spec).sort_values("acquired_at_utc", ascending=False).head(limit)
    columns = [column for column in DETECTION_COLUMNS if column in filtered.columns]
    csv_data = filtered[columns].to_csv(index=False)
    filename = f"fuegoclaro_detecciones_{spec.start_date}_{spec.end_date}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Data-Mode": store.mode,
            "X-Dataset-Version": str(store.manifest.get("dataset_version", "")),
        },
    )
