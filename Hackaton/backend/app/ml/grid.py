"""Cuadrícula espacial común para el dataset de riesgo.

Unidad: celda de ``step`` grados (por defecto 0.1°, ~11 km) x día local.
La celda se identifica por los índices enteros ``lat_idx``/``lon_idx`` y su
centro se calcula con ``(idx + 0.5) * step``. Todas las fuentes externas
(clima, DEM, NDVI) se consultan en ese centro para que el cruce sea exacto.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd
import shapely

from app.utils.geo import load_province_features

DEFAULT_GRID_STEP = 0.1
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Cell:
    cell_id: str
    lat_idx: int
    lon_idx: int
    lat: float
    lon: float


def cell_id(lat_idx: int, lon_idx: int) -> str:
    return f"{int(lat_idx)}_{int(lon_idx)}"


def cell_indices(latitude, longitude, step: float = DEFAULT_GRID_STEP) -> tuple[np.ndarray, np.ndarray]:
    """Índices de celda (enteros) para uno o varios puntos."""
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    return np.floor(lat / step).astype(np.int64), np.floor(lon / step).astype(np.int64)


def cell_centers(lat_idx, lon_idx, step: float = DEFAULT_GRID_STEP) -> tuple[np.ndarray, np.ndarray]:
    lat = (np.asarray(lat_idx, dtype=float) + 0.5) * step
    lon = (np.asarray(lon_idx, dtype=float) + 0.5) * step
    return lat, lon


def assign_cell_ids(frame: pd.DataFrame, step: float = DEFAULT_GRID_STEP) -> pd.DataFrame:
    """Añade ``lat_idx``, ``lon_idx`` y ``cell_id`` a un DataFrame con lat/lon."""
    out = frame.copy()
    lat_idx, lon_idx = cell_indices(out["latitude"].to_numpy(), out["longitude"].to_numpy(), step=step)
    out["lat_idx"] = lat_idx
    out["lon_idx"] = lon_idx
    out["cell_id"] = [cell_id(a, b) for a, b in zip(lat_idx, lon_idx)]
    return out


def _province_union():
    features = load_province_features()
    geometries = [shapely.geometry.shape(feature["geometry"]) for feature in features]
    if not geometries:
        return None, features
    return shapely.union_all(geometries), features


@lru_cache(maxsize=4)
def land_cells(step: float = DEFAULT_GRID_STEP) -> pd.DataFrame:
    """Celdas cuyo centro cae dentro de alguna provincia de Ecuador.

    Devuelve columnas: ``cell_id``, ``lat_idx``, ``lon_idx``, ``lat``, ``lon``,
    ``province``, ``province_id``, ``region``, ``region_id``, ``is_galapagos``.
    """
    union, features = _province_union()
    if union is None:
        raise RuntimeError(
            "No se encontró data/regions/ecuador_provinces.geojson; "
            "no es posible construir la cuadrícula terrestre."
        )

    west, south, east, north = union.bounds
    lat_start = int(np.floor(south / step))
    lat_stop = int(np.ceil(north / step))
    lon_start = int(np.floor(west / step))
    lon_stop = int(np.ceil(east / step))

    lat_idx_grid, lon_idx_grid = np.meshgrid(
        np.arange(lat_start, lat_stop),
        np.arange(lon_start, lon_stop),
        indexing="ij",
    )
    lat_idx = lat_idx_grid.ravel()
    lon_idx = lon_idx_grid.ravel()
    lat, lon = cell_centers(lat_idx, lon_idx, step=step)

    inside = shapely.contains_xy(union, lon, lat)
    lat_idx = lat_idx[inside]
    lon_idx = lon_idx[inside]
    lat = lat[inside]
    lon = lon[inside]

    province = np.full(len(lat), None, dtype=object)
    province_id = np.full(len(lat), None, dtype=object)
    region = np.full(len(lat), None, dtype=object)
    region_id = np.full(len(lat), None, dtype=object)

    for feature in features:
        props = feature["properties"]
        geom = shapely.geometry.shape(feature["geometry"])
        mask = shapely.contains_xy(geom, lon, lat) & (province_id == None)  # noqa: E711
        if not mask.any():
            continue
        iso = props.get("iso_3166_2") or props.get("iso") or ""
        name = props.get("name") or "Desconocida"
        natural = props.get("region_id") or "desconocida"
        province[mask] = name
        province_id[mask] = _slug(iso or name)
        region[mask] = props.get("region") or natural
        region_id[mask] = natural

    frame = pd.DataFrame(
        {
            "lat_idx": lat_idx,
            "lon_idx": lon_idx,
            "lat": lat,
            "lon": lon,
            "province": province,
            "province_id": province_id,
            "region": region,
            "region_id": region_id,
        }
    )
    frame["province"] = frame["province"].fillna("Desconocida")
    frame["province_id"] = frame["province_id"].fillna("desconocida")
    frame["region"] = frame["region"].fillna("Desconocida")
    frame["region_id"] = frame["region_id"].fillna("desconocida")
    frame["cell_id"] = [
        cell_id(a, b) for a, b in zip(frame["lat_idx"], frame["lon_idx"])
    ]
    frame["is_galapagos"] = (frame["region_id"] == "galapagos").astype("int8")
    frame = frame.sort_values(["lat_idx", "lon_idx"]).reset_index(drop=True)
    return frame[
        [
            "cell_id",
            "lat_idx",
            "lon_idx",
            "lat",
            "lon",
            "province",
            "province_id",
            "region",
            "region_id",
            "is_galapagos",
        ]
    ]


def _slug(value: str) -> str:
    import unicodedata

    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_value = "".join(c for c in normalized if not unicodedata.combining(c))
    return ascii_value.lower().replace(" ", "-").replace("_", "-")


def neighbor_offsets(rings: int = 1) -> list[tuple[int, int]]:
    """Desplazamientos (dlat, dlon) del vecindario cuadrado, sin incluir (0, 0)."""
    return [
        (dlat, dlon)
        for dlat in range(-rings, rings + 1)
        for dlon in range(-rings, rings + 1)
        if not (dlat == 0 and dlon == 0)
    ]


def cell_to_neighbors(cells: pd.DataFrame, rings: int = 1) -> dict[str, list[str]]:
    """Mapa ``cell_id -> cell_ids vecinos`` que existen en la cuadrícula."""
    known = {
        (int(row.lat_idx), int(row.lon_idx)): str(row.cell_id)
        for row in cells.itertuples(index=False)
    }
    mapping: dict[str, list[str]] = {}
    for row in cells.itertuples(index=False):
        values = []
        for dlat, dlon in neighbor_offsets(rings):
            key = (int(row.lat_idx) + dlat, int(row.lon_idx) + dlon)
            if key in known:
                values.append(known[key])
        mapping[str(row.cell_id)] = values
    return mapping


def nearest_cell(latitude: float, longitude: float, cells: pd.DataFrame) -> tuple[str, float]:
    """Celda terrestre más cercana y distancia en km."""
    distances = haversine_km(
        np.full(len(cells), float(latitude)),
        np.full(len(cells), float(longitude)),
        cells["lat"].to_numpy(),
        cells["lon"].to_numpy(),
    )
    position = int(np.argmin(distances))
    return str(cells.iloc[position]["cell_id"]), float(distances[position])


def haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    """Distancia haversine vectorizada en kilómetros."""
    lat1r, lon1r = np.radians(lat1), np.radians(lon1)
    lat2r, lon2r = np.radians(lat2), np.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2.0) ** 2
    return EARTH_RADIUS_KM * 2.0 * np.arcsin(np.clip(np.sqrt(a), 0.0, 1.0))
