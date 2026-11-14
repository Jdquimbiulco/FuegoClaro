"""Endpoints de sistema."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.data_store import get_store
from app.utils.json_safe import json_safe

router = APIRouter(tags=["sistema"])


@router.get("/health")
def health() -> dict:
    store = get_store()
    meta = store.meta
    start, end = store.date_bounds()
    settings = get_settings()
    return json_safe(
        {
            "status": "ok" if meta.rows > 0 else "degraded",
            "app": settings.app_name,
            "version": settings.version,
            "data_mode": meta.mode,
            "rows": meta.rows,
            "date_range": {"start": start, "end": end},
            "loaded_at": meta.loaded_at,
            "checks": {
                "dataset": "ok" if meta.rows > 0 else "empty",
                "firms_key": "configured" if settings.firms_map_key else "missing",
                "regions": "ok" if (settings.regions_dir / "ecuador_provinces.geojson").exists() else "missing",
            },
            "notes": []
            if meta.rows > 0
            else ["No hay dataset procesado ni muestra. Ejecuta scripts/ingest_firms.py."],
        }
    )
