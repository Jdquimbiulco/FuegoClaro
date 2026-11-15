"""Metadatos del dataset, cobertura y catálogo de regiones."""

from __future__ import annotations

from fastapi import APIRouter

from app.services.data_store import get_store
from app.utils.geo import ecuador_geojson, regions_payload
from app.utils.json_safe import json_safe

router = APIRouter(tags=["metadatos"])


@router.get("/meta")
def meta() -> dict:
    return json_safe(get_store().meta_payload())


@router.get("/regions")
def regions() -> dict:
    store = get_store()
    payload = regions_payload()
    df = store.df
    if not df.empty:
        region_counts = df["region_id"].value_counts().to_dict()
        province_counts = df["province_id"].value_counts().to_dict()
        canton_counts = df["canton_id"].value_counts(dropna=True).to_dict() if "canton_id" in df else {}
        for region in payload["regions"]:
            region["count"] = int(region_counts.get(region["id"], 0))
        for province in payload["provinces"]:
            province["count"] = int(province_counts.get(province["id"], 0))
        for canton in payload.get("cantons", []):
            canton["count"] = int(canton_counts.get(canton["id"], 0))
    return json_safe(payload)


@router.get("/regions/geojson")
def regions_geojson() -> dict:
    return ecuador_geojson()


@router.get("/provenance")
def provenance() -> dict:
    store = get_store()
    meta = store.meta
    return json_safe(
        {
            "data_mode": meta.mode,
            "loaded_at": meta.loaded_at,
            "path": meta.path,
            "manifest": meta.manifest,
        }
    )
