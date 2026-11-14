"""Consulta de detecciones individuales y GeoJSON para el mapa."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import common_filters, response_meta
from app.domain.models import FilterSpec
from app.services.data_store import apply_filters, get_store
from app.utils.json_safe import json_safe, records

router = APIRouter(tags=["detecciones"])

DETECTION_COLUMNS = [
    "id",
    "sensor",
    "satellite",
    "instrument",
    "source_product",
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "acq_date_local",
    "acq_time_local",
    "acquired_at_utc",
    "daynight",
    "confidence_level",
    "confidence_raw",
    "confidence_score",
    "frp",
    "brightness",
    "bright_t31",
    "bright_ti5",
    "scan",
    "track",
    "version",
    "type",
    "province",
    "province_id",
    "region",
    "region_id",
    "provenance_id",
]


@router.get("/detections")
def detections(
    spec: FilterSpec = Depends(common_filters),
    limit: int = Query(5000, ge=1, le=20000),
    offset: int = Query(0, ge=0),
    format: str = Query("json", pattern="^(json|geojson)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
) -> dict:
    store = get_store()
    filtered = apply_filters(store.df, spec)
    total = int(len(filtered))
    if total == 0:
        empty = {"type": "FeatureCollection", "features": []} if format == "geojson" else []
        return json_safe(
            {
                "meta": response_meta(
                    store,
                    spec,
                    notes=["No hay detecciones para los filtros seleccionados."],
                ),
                "pagination": {"total": 0, "limit": limit, "offset": offset, "returned": 0, "truncated": False},
                "data": empty,
            }
        )

    filtered = filtered.sort_values("acquired_at_utc", ascending=(order == "asc"))
    page = filtered.iloc[offset : offset + limit]
    page_columns = [column for column in DETECTION_COLUMNS if column in page.columns]

    if format == "geojson":
        features = []
        for row in records(page[page_columns]):
            coordinates = [row["longitude"], row["latitude"]]
            properties = {key: value for key, value in row.items() if key not in ("longitude", "latitude")}
            features.append({"type": "Feature", "geometry": {"type": "Point", "coordinates": coordinates}, "properties": properties})
        data = {"type": "FeatureCollection", "features": features}
    else:
        data = records(page[page_columns])

    notes = []
    if offset + len(page) < total:
        notes.append("Resultado paginado: usa limit/offset o reduce el periodo para ver más registros.")
    return json_safe(
        {
            "meta": response_meta(store, spec, notes=notes),
            "pagination": {
                "total": total,
                "limit": limit,
                "offset": offset,
                "returned": int(len(page)),
                "truncated": offset + len(page) < total,
            },
            "data": data,
        }
    )


@router.get("/detections/{detection_id}")
def detection_detail(detection_id: str) -> dict:
    store = get_store()
    df = store.df
    match = df[df["id"] == detection_id]
    if match.empty:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Detección no encontrada"})
    page_columns = [column for column in DETECTION_COLUMNS if column in match.columns]
    return json_safe({"data": records(match[page_columns])[0], "meta": {"data_mode": store.mode}})
