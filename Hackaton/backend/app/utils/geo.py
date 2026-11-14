"""Utilidades geoespaciales: regiones de Ecuador y asignación de puntos."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from shapely.geometry import shape

from app.core.config import get_settings
from app.domain.models import NATURAL_REGIONS, PROVINCES


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_value.lower().replace(" ", "-").replace("_", "-")


def province_slug(iso_code: str) -> str:
    name = PROVINCES.get(iso_code, (iso_code, ""))[0]
    return slugify(name)


@lru_cache
def regions_file() -> Path:
    return get_settings().regions_dir / "ecuador_provinces.geojson"


@lru_cache
def load_province_features() -> list[dict]:
    path = regions_file()
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        collection = json.load(handle)
    return list(collection.get("features", []))


@lru_cache
def load_province_geometries() -> list[tuple[dict, shapely.Geometry]]:
    features = load_province_features()
    return [(feature["properties"], shape(feature["geometry"])) for feature in features]


def assign_provinces(df: pd.DataFrame) -> pd.DataFrame:
    """Asigna provincia/región natural a cada detección.

    Solo se consideran puntos dentro de las geometrías provinciales de Ecuador.
    Puntos en océano o países vecinos quedan como 'outside' y se excluyen del dataset.
    """
    if df.empty:
        df["province"] = pd.Series(dtype="object")
        df["province_id"] = pd.Series(dtype="object")
        df["region"] = pd.Series(dtype="object")
        df["region_id"] = pd.Series(dtype="object")
        return df

    lon = df["longitude"].to_numpy()
    lat = df["latitude"].to_numpy()
    province = np.full(len(df), None, dtype=object)
    province_id = np.full(len(df), None, dtype=object)
    region = np.full(len(df), None, dtype=object)
    region_id = np.full(len(df), None, dtype=object)

    for props, geom in load_province_geometries():
        # shapely.contains_xy es vectorizado y rápido; se evalúa solo donde falta asignar.
        mask = shapely.contains_xy(geom, lon, lat)
        if not mask.any():
            continue
        mask = mask & (province_id == None)  # noqa: E711
        if not mask.any():
            continue
        iso = props.get("iso_3166_2") or props.get("iso")
        canonical_name = props.get("name") or "Desconocida"
        natural_id = props.get("region_id") or "desconocida"
        province[mask] = canonical_name
        province_id[mask] = province_slug(iso) if iso else slugify(canonical_name)
        region[mask] = NATURAL_REGIONS.get(natural_id, {}).get("name", natural_id)
        region_id[mask] = natural_id

    df = df.copy()
    df["province"] = province
    df["province_id"] = province_id
    df["region"] = region
    df["region_id"] = region_id
    df.loc[df["region_id"].isna(), "region_id"] = "outside"
    df.loc[df["region_id"] == "outside", "region"] = "Fuera de Ecuador"
    return df


def regions_payload() -> dict:
    """Metadatos de regiones para el frontend (sin geometrías completas)."""
    features = load_province_features()
    provinces = []
    for feature in features:
        props = feature["properties"]
        geom = shape(feature["geometry"])
        centroid = geom.representative_point()
        provinces.append(
            {
                "id": province_slug(props.get("iso_3166_2", "")),
                "iso": props.get("iso_3166_2"),
                "name": props.get("name"),
                "region_id": props.get("region_id"),
                "region": NATURAL_REGIONS.get(props.get("region_id", ""), {}).get("name", props.get("region_id")),
                "bbox": list(geom.bounds),
                "center": [centroid.y, centroid.x],
            }
        )

    natural = []
    for region_id, meta in NATURAL_REGIONS.items():
        members = [p for p in provinces if p["region_id"] == region_id]
        if not members:
            continue
        bounds = np.array([p["bbox"] for p in members])
        bbox = [
            float(bounds[:, 0].min()),
            float(bounds[:, 1].min()),
            float(bounds[:, 2].max()),
            float(bounds[:, 3].max()),
        ]
        natural.append(
            {
                "id": region_id,
                "name": meta["name"],
                "description": meta["description"],
                "bbox": bbox,
                "center": [float((bbox[1] + bbox[3]) / 2), float((bbox[0] + bbox[2]) / 2)],
                "provinces": [p["id"] for p in members],
            }
        )
    return {"regions": natural, "provinces": provinces}


def ecuador_geojson() -> dict:
    path = regions_file()
    if not path.exists():
        return {"type": "FeatureCollection", "features": []}
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)
