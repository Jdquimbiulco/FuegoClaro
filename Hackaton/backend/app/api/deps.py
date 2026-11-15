"""Dependencias compartidas de la API: filtros comunes y metadatos de respuesta."""

from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, Query

from app.domain.models import FilterSpec
from app.services.data_store import DataStore, get_store
from app.utils.geo import regions_payload
from app.utils.time import parse_iso_date


@lru_cache
def allowed_region_ids() -> set[str]:
    payload = regions_payload()
    ids = {region["id"] for region in payload["regions"]}
    ids.update(province["id"] for province in payload["provinces"])
    return ids


def parse_bbox(value: str | None) -> tuple[float, float, float, float] | None:
    if not value:
        return None
    try:
        parts = tuple(float(item) for item in value.split(","))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bbox debe ser west,south,east,north") from exc
    if len(parts) != 4:
        raise HTTPException(status_code=400, detail="bbox debe tener 4 valores: west,south,east,north")
    west, south, east, north = parts
    if west >= east or south >= north:
        raise HTTPException(status_code=400, detail="bbox inválido: west<east y south<north")
    return parts  # type: ignore[return-value]


def common_filters(
    start_date: str | None = Query(None, description="Fecha inicial local YYYY-MM-DD (por defecto, últimos 365 días)"),
    end_date: str | None = Query(None, description="Fecha final local YYYY-MM-DD"),
    region_id: str | None = Query(None, description="Región natural (costa/sierra/amazonia/galapagos), provincia o 'all'"),
    canton_id: str | None = Query(None, description="Código DPA oficial del cantón"),
    sensor: str | None = Query("all", description="MODIS, VIIRS o all"),
    confidence: str | None = Query(None, description="Niveles separados por coma: low,nominal,high,unknown"),
    daynight: str | None = Query(None, description="D o N"),
    min_frp: float | None = Query(None, ge=0, description="FRP mínimo en MW"),
    bbox: str | None = Query(None, description="west,south,east,north"),
) -> FilterSpec:
    store = get_store()
    default_start, default_end = store.default_window()
    start = start_date or default_start
    end = end_date or default_end
    try:
        start_parsed = parse_iso_date(start, "start_date")
        end_parsed = parse_iso_date(end, "end_date")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if end_parsed < start_parsed:
        raise HTTPException(status_code=400, detail="end_date no puede ser anterior a start_date")

    sensor_value = (sensor or "all").strip()
    if sensor_value not in ("all", "MODIS", "VIIRS"):
        raise HTTPException(status_code=400, detail="sensor debe ser MODIS, VIIRS o all")

    region_value = (region_id or "all").strip()
    if region_value not in ("all", "ecuador") and region_value not in allowed_region_ids():
        raise HTTPException(status_code=400, detail=f"region_id desconocido: {region_value}")

    confidence_values: list[str] = []
    if confidence:
        confidence_values = [item.strip().lower() for item in confidence.split(",") if item.strip()]
        invalid = [item for item in confidence_values if item not in ("low", "nominal", "high", "unknown")]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Niveles de confianza inválidos: {', '.join(invalid)}")

    daynight_value = (daynight or "").upper() or None
    if daynight_value and daynight_value not in ("D", "N"):
        raise HTTPException(status_code=400, detail="daynight debe ser D o N")

    canton_value = (canton_id or "").strip() or None
    canton_ids = {item["id"] for item in regions_payload().get("cantons", [])}
    if canton_value and canton_value not in canton_ids:
        raise HTTPException(status_code=400, detail=f"canton_id desconocido: {canton_value}")
    return FilterSpec(
        start_date=start_parsed.isoformat(),
        end_date=end_parsed.isoformat(),
        region_id=region_value,
        canton_id=canton_value,
        sensor=sensor_value,
        confidence=confidence_values,
        daynight=daynight_value,
        min_frp=min_frp,
        bbox=parse_bbox(bbox),
    )


def response_meta(store: DataStore, spec: FilterSpec, *, notes: list[str] | None = None) -> dict:
    manifest = store.manifest
    return {
        "data_mode": store.mode,
        "dataset_version": manifest.get("dataset_version"),
        "generated_at": manifest.get("generated_at"),
        "period": {"start": spec.start_date, "end": spec.end_date},
        "filters": {
            "region_id": spec.region_id,
            "canton_id": spec.canton_id,
            "sensor": spec.sensor,
            "confidence": spec.confidence,
            "daynight": spec.daynight,
            "min_frp": spec.min_frp,
            "bbox": list(spec.bbox) if spec.bbox else None,
        },
        "attribution": manifest.get("attribution", "NASA FIRMS"),
        "notes": notes or [],
    }
