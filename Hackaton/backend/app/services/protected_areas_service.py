"""Lectura e intersección de las áreas protegidas SNAP."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

from app.core.config import get_settings
from app.core.errors import ModuleContractError


def _path():
    return get_settings().regions_dir / "protected_areas_snap_ec.geojson"


def _properties(props: dict[str, Any], index: int) -> dict[str, Any]:
    code = str(props.get("csnap") or props.get("fcode") or index + 1)
    return {
        **props,
        "area_id": f"snap-{code}",
        "name": str(props.get("nam") or "Área protegida sin nombre"),
        "category": str(props.get("map") or "Sin categoría"),
        "subsystem": str(props.get("subap") or "Sin subsistema"),
    }


@lru_cache(maxsize=1)
def _catalog() -> tuple[list[dict], list[shapely.Geometry], STRtree]:
    path = _path()
    if not path.exists():
        raise ModuleContractError("protected_areas", f"No existe el archivo {path.name}.")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        features = payload.get("features", [])
        if payload.get("type") != "FeatureCollection" or not isinstance(features, list):
            raise ValueError("Se esperaba un FeatureCollection GeoJSON.")
        normalized = []
        geometries = []
        for index, feature in enumerate(features):
            geometry = shape(feature["geometry"])
            if geometry.is_empty:
                continue
            normalized.append({"type": "Feature", "geometry": feature["geometry"], "properties": _properties(feature.get("properties", {}), index)})
            geometries.append(geometry)
        return normalized, geometries, STRtree(geometries)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise ModuleContractError("protected_areas", f"GeoJSON SNAP inválido: {exc}") from exc


def geojson() -> dict:
    features, _, _ = _catalog()
    return {
        "type": "FeatureCollection",
        "features": features,
        "notes": ["Fuente: Sistema Nacional de Áreas Protegidas (SNAP), Ecuador.", "La capa es contexto ambiental; no delimita superficie afectada."],
    }


def intersecting_areas(geometry: dict) -> list[dict]:
    """Devuelve áreas que intersectan la geometría; usa índice espacial."""
    features, geometries, tree = _catalog()
    target = shape(geometry)
    indexes = tree.query(target, predicate="intersects")
    return [features[int(index)] for index in indexes if geometries[int(index)].intersects(target)]


def status() -> dict:
    try:
        features, _, _ = _catalog()
        return {"name": "protected_areas", "status": "available", "areas": len(features), "artifact": str(_path())}
    except ModuleContractError as exc:
        return {"name": "protected_areas", "status": "error", "areas": 0, "artifact": None, "detail": exc.details.get("detail")}
