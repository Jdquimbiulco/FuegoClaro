"""Lectura incremental e intersección exacta de las áreas protegidas SNAP."""
from __future__ import annotations

import json
import zlib
from dataclasses import dataclass
from functools import lru_cache
from threading import RLock
from typing import Any

import ijson
import shapely
from shapely.geometry import shape
from shapely.strtree import STRtree

from app.core.config import get_settings
from app.core.errors import ModuleContractError
from app.utils.json_safe import json_safe

_NOTES = ["Fuente: Sistema Nacional de Áreas Protegidas (SNAP), Ecuador.", "La capa es contexto ambiental; no delimita superficie afectada."]
_catalog_lock = RLock()


def _path():
    return get_settings().regions_dir / "protected_areas_snap_ec.geojson"


def _properties(props: dict[str, Any], index: int) -> dict[str, Any]:
    code = str(props.get("csnap") or props.get("fcode") or index + 1)
    return {**props, "area_id": f"snap-{code}",
            "name": str(props.get("nam") or "Área protegida sin nombre"),
            "category": str(props.get("map") or "Sin categoría"),
            "subsystem": str(props.get("subap") or "Sin subsistema")}


@dataclass(frozen=True)
class _Feature:
    properties: dict
    original: bytes
    response: bytes

    def unpack(self) -> dict:
        return json.loads(zlib.decompress(self.original))


def _compressed(value) -> bytes:
    return zlib.compress(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode(), level=1)


@lru_cache(maxsize=1)
def _catalog() -> tuple[list[_Feature], list[shapely.Geometry], STRtree]:
    path = _path()
    if not path.exists():
        raise ModuleContractError("protected_areas", f"No existe el archivo {path.name}.")
    try:
        # Validate the envelope without ever materializing the complete tree.
        with path.open("rb") as handle:
            collection_type = next(ijson.items(handle, "type", use_float=True), None)
        if collection_type != "FeatureCollection":
            raise ValueError("Se esperaba un FeatureCollection GeoJSON.")
        normalized, geometries = [], []
        with path.open("rb") as handle:
            for index, feature in enumerate(ijson.items(handle, "features.item", use_float=True)):
                geometry = shape(feature["geometry"])
                if geometry.is_empty:
                    continue
                props = _properties(feature.get("properties", {}), index)
                item = {"type": "Feature", "geometry": feature["geometry"], "properties": props}
                normalized.append(_Feature(props, _compressed(item), _compressed(json_safe(item))))
                geometries.append(geometry)
        return normalized, geometries, STRtree(geometries)
    except (OSError, ValueError, KeyError, ijson.JSONError) as exc:
        raise ModuleContractError("protected_areas", f"GeoJSON SNAP inválido: {exc}") from exc


def _get_catalog():
    # lru_cache alone permits concurrent duplicate cold builds.
    with _catalog_lock:
        return _catalog()


def geojson() -> dict:
    features, _, _ = _get_catalog()
    return {"type": "FeatureCollection", "features": [item.unpack() for item in features], "notes": list(_NOTES)}


def stream_response():
    """Bounded wire chunks, with the same six-decimal JSON contract as before."""
    features, _, _ = _get_catalog()
    meta = json.dumps(json_safe({"module": status(), "notes": _NOTES}), ensure_ascii=False, separators=(",", ":")).encode()
    yield b'{"meta":' + meta + b',"data":{"type":"FeatureCollection","features":['
    for index, feature in enumerate(features):
        if index:
            yield b","
        decoder = zlib.decompressobj()
        pending = feature.response
        while pending:
            chunk = decoder.decompress(pending, 65536)
            pending = decoder.unconsumed_tail
            if chunk:
                yield chunk
        final = decoder.flush()
        if final:
            yield final
    yield b"]}}"


def intersecting_areas(geometry: dict, *, include_geometry: bool = True) -> list[dict]:
    """Exact original Shapely geometry; alerts only need properties."""
    features, geometries, tree = _get_catalog()
    target = shape(geometry)
    indexes = tree.query(target, predicate="intersects")
    return [features[int(index)].unpack() if include_geometry else {"properties": features[int(index)].properties}
            for index in indexes if geometries[int(index)].intersects(target)]


def status() -> dict:
    try:
        features, _, _ = _get_catalog()
        return {"name": "protected_areas", "status": "available", "areas": len(features), "artifact": str(_path())}
    except ModuleContractError as exc:
        return {"name": "protected_areas", "status": "error", "areas": 0, "artifact": None, "detail": exc.details.get("detail")}
