"""Entregable Persona 2: detección de eventos de incendio desde detecciones FIRMS.

Función principal: ``detect_fire_events(df_detections) -> list[dict]``

Flujo:
1. Normaliza columnas (acepta esquema canónico de FuegoClaro o CSV crudo FIRMS).
2. Excluye mecheros petroleros: puntos a <= ``flare_radius_km`` de coordenadas
   fijas (lista en ``data/regions/mecheros_petroleros.json``, reemplazable por
   la lista oficial).
3. ST-DBSCAN: agrupa por espacio (``eps_km``, por defecto 2) y ventana temporal
   (``eps_days``; 1 = 24 h, 2 = 48 h).
4. Métricas por cluster: ``frp_total``, ``frp_max``, ``puntos_count``,
   ``geometria`` (Convex Hull GeoJSON; bounding box como respaldo).
5. Motor de reglas:
   - ``alerta_roja``: FRP total > 100 MW O detección nocturna (daynight == 'N').
   - ``alerta_media``: FRP moderado (10-100 MW) o grupo multi-punto/día.
   - ``quema_menor``: puntos individuales o grupos pequeños de bajo FRP (< 10 MW) diurnos.
"""

from __future__ import annotations

import json
from hashlib import sha1
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
import shapely

from app.core.config import get_settings
from app.domain.fire_evidence import _thermal_contrast

DEFAULT_EPS_KM = 2.0
DEFAULT_EPS_DAYS = 1
DEFAULT_FLARE_RADIUS_KM = 3.0

ALERT_LEVELS = ("alerta_roja", "alerta_media", "quema_menor")

_ALERT_LABELS = {
    "alerta_roja": "Alerta Roja / Crítica",
    "alerta_media": "Alerta Media",
    "quema_menor": "Quema Menor / Agrícola",
}

_FRP_ROJA_MW = 100.0
_FRP_MEDIA_MW = 10.0

# Coordenadas aproximadas de centros de campos petroleros con mecheros en
# Sucumbíos/Orellana. Se usan solo si no existe el archivo oficial
# mecheros_petroleros.json (reemplazarlo con la lista provista).
_DEFAULT_FLARES = [
    {"name": "Shushufindi", "lat": -0.133, "lon": -76.633},
    {"name": "Libertador", "lat": -0.530, "lon": -76.630},
    {"name": "Sacha", "lat": -0.480, "lon": -76.620},
    {"name": "Auca", "lat": -0.520, "lon": -76.780},
    {"name": "Lago Agrio", "lat": 0.080, "lon": -76.800},
    {"name": "Indillama", "lat": -0.550, "lon": -76.710},
    {"name": "Aguarico", "lat": -0.280, "lon": -76.150},
]


# --------------------------------------------------------------------------- geometría y ST-DBSCAN
def _haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Distancia haversine vectorizada en kilómetros."""
    lat1r, lon1r = np.radians(lat1), np.radians(lon1)
    lat2r, lon2r = np.radians(lat2), np.radians(lon2)
    dlat = lat2r - lat1r
    dlon = lon2r - lon1r
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1r) * np.cos(lat2r) * np.sin(dlon / 2.0) ** 2
    return 6371.0088 * 2.0 * np.arcsin(np.clip(np.sqrt(a), 0.0, 1.0))


def _degrees_for_km(eps_km: float) -> float:
    """Celda de rejilla en grados que contiene cualquier punto a <= eps_km."""
    return max(eps_km / 111.32, 1e-6)


def _neighbour_pairs(
    lat: np.ndarray,
    lon: np.ndarray,
    day_ord: np.ndarray,
    eps_km: float,
    eps_days: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Pares índice (i, j), i < j, a <= eps_km y <= eps_days.

    Búsqueda por rejilla: celdas de lado eps_deg y vecindad 3x3 en el plano;
    la verificación exacta (haversine + días) se hace solo sobre candidatos.
    """
    eps_deg = _degrees_for_km(eps_km)
    lat_cell = np.floor(lat / eps_deg).astype("int64")
    lon_cell = np.floor(lon / eps_deg).astype("int64")

    keys = pd.DataFrame(
        {"row": np.arange(len(lat)), "lat_cell": lat_cell, "lon_cell": lon_cell, "day_ord": day_ord}
    )
    left_rows: list[np.ndarray] = []
    right_rows: list[np.ndarray] = []

    # Se usa solamente la mitad canónica de los desplazamientos. Antes se
    # formaban pares de todos los días de una misma celda espacial y recién
    # después se descartaban; en una ventana anual eso podía crecer a O(n²).
    # Incluir day_ord en la llave limita los candidatos a la ventana temporal
    # solicitada antes de calcular distancia o crear la lista de adyacencia.
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            for dday in range(-eps_days, eps_days + 1):
                # La comparación lexicográfica deja cada par espacial-temporal
                # en un único desplazamiento; el origen se trata aparte.
                if (dlat, dlon, dday) < (0, 0, 0):
                    continue
                probe = keys[["row", "lat_cell", "lon_cell", "day_ord"]].copy()
                probe["lat_cell"] += dlat
                probe["lon_cell"] += dlon
                probe["day_ord"] += dday
                merged = probe.merge(
                    keys.rename(columns={"row": "row2"}),
                    on=["lat_cell", "lon_cell", "day_ord"],
                    how="inner",
                )
                if merged.empty:
                    continue
                i_values = merged["row"].to_numpy()
                j_values = merged["row2"].to_numpy()
                if (dlat, dlon, dday) == (0, 0, 0):
                    keep = i_values < j_values
                    i_values, j_values = i_values[keep], j_values[keep]
                if i_values.size:
                    left_rows.append(i_values)
                    right_rows.append(j_values)

    if not left_rows:
        return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.int64)

    i = np.concatenate(left_rows)
    j = np.concatenate(right_rows)
    dist = _haversine_km(lat[i], lon[i], lat[j], lon[j])
    keep = dist <= eps_km
    return i[keep], j[keep]


def _connected_components(lat, lon, day_ord, eps_km, eps_days):
    """min_points=1 is connected components, with bounded candidate tiles.

    Preserve the original 3x3 grid, day offsets, haversine predicate and
    component order. No distance approximation or geometry simplification.
    """
    n = len(lat)
    eps_deg = _degrees_for_km(eps_km)
    buckets = {}
    for index, key in enumerate(zip(np.floor(lat / eps_deg).astype("int64"),
                                    np.floor(lon / eps_deg).astype("int64"), day_ord)):
        buckets.setdefault(tuple(key), []).append(index)
    buckets = {key: np.asarray(rows, dtype=np.int64) for key, rows in buckets.items()}
    parent = list(range(n))

    def root(index):
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    offsets = [(a, b, c) for a in (-1, 0, 1) for b in (-1, 0, 1)
               for c in range(-eps_days, eps_days + 1) if (a, b, c) >= (0, 0, 0)]
    for (a, b, c), rows in buckets.items():
        for da, db, dc in offsets:
            other = buckets.get((a + da, b + db, c + dc))
            if other is None:
                continue
            for start in range(0, len(rows), 128):
                first = rows[start:start + 128]
                for end in range(0, len(other), 128):
                    second = other[end:end + 128]
                    i = np.repeat(first, len(second))
                    j = np.tile(second, len(first))
                    if (da, db, dc) == (0, 0, 0):
                        keep = i < j
                        i, j = i[keep], j[keep]
                    if not len(i):
                        continue
                    keep = _haversine_km(lat[i], lon[i], lat[j], lon[j]) <= eps_km
                    for left, right in zip(i[keep].tolist(), j[keep].tolist()):
                        ra, rb = root(left), root(right)
                        if ra != rb:
                            parent[max(ra, rb)] = min(ra, rb)
    labels = np.empty(n, dtype=np.int64)
    numbering = {}
    for index in range(n):
        representative = root(index)
        labels[index] = numbering.setdefault(representative, len(numbering))
    return labels


def _dbscan_st(
    lat: np.ndarray,
    lon: np.ndarray,
    day_ord: np.ndarray,
    eps_km: float,
    eps_days: int,
    min_points: int,
) -> np.ndarray:
    """DBSCAN (eps_km, eps_days, min_points) con lista de adyacencia por pares."""
    n = len(lat)
    labels = np.full(n, -1, dtype=np.int64)
    if n == 0:
        return labels

    if min_points == 1:
        return _connected_components(lat, lon, day_ord, eps_km, eps_days)

    pair_i, pair_j = _neighbour_pairs(lat, lon, day_ord, eps_km, eps_days)

    neighbours: list[set[int]] = [set() for _ in range(n)]
    for a, b in zip(pair_i.tolist(), pair_j.tolist()):
        neighbours[a].add(b)
        neighbours[b].add(a)

    visited = np.zeros(n, dtype=bool)
    cluster_id = 0
    for start in range(n):
        if visited[start]:
            continue
        visited[start] = True
        region = {start} | neighbours[start]
        if len(region) < min_points:
            continue  # ruido (puede ser alcanzado luego como borde)
        queue = deque(x for x in region if x != start)
        labels[list(region)] = cluster_id
        while queue:
            point = queue.popleft()
            if visited[point]:
                continue
            visited[point] = True
            region_p = {point} | neighbours[point]
            if len(region_p) >= min_points:
                labels[point] = cluster_id
                for nxt in region_p:
                    if labels[nxt] == -1 or not visited[nxt]:
                        labels[nxt] = cluster_id
                        if not visited[nxt]:
                            queue.append(nxt)
        cluster_id += 1
    return labels


def _flare_file() -> Path:
    return get_settings().regions_dir / "mecheros_petroleros.json"


def load_flare_sources(flare_file: Path | None = None) -> list[dict]:
    """Lista de mecheros: archivo local si existe; si no, lista aproximada por defecto."""
    path = flare_file or _flare_file()
    if path.exists():
        try:
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            sources = payload.get("sources", payload) if isinstance(payload, dict) else payload
            parsed = [
                {"name": str(item.get("name", f"mechero-{i}")), "lat": float(item["lat"]), "lon": float(item["lon"])}
                for i, item in enumerate(sources)
                if "lat" in item and "lon" in item
            ]
            if parsed:
                return parsed
        except (OSError, json.JSONDecodeError, TypeError, ValueError, KeyError):
            pass
    return [dict(item) for item in _DEFAULT_FLARES]


def _flare_mask(lat: np.ndarray, lon: np.ndarray, sources: list[dict], radius_km: float) -> np.ndarray:
    """True para puntos a <= radius_km de algún mechero (coordenadas fijas)."""
    excluded = np.zeros(len(lat), dtype=bool)
    if not sources or len(lat) == 0:
        return excluded
    for source in sources:
        dist = _haversine_km(lat, lon, np.full(len(lat), source["lat"]), np.full(len(lat), source["lon"]))
        excluded |= dist <= radius_km
    return excluded


def _date_column(df: pd.DataFrame) -> pd.Series:
    for column in ("acq_date_local", "acq_date", "acquired_at_utc"):
        if column in df.columns:
            return df[column].astype(str)
    return pd.Series([""] * len(df), index=df.index)


def _convex_hull_geojson(lat: np.ndarray, lon: np.ndarray) -> dict:
    """Convex Hull de las detecciones del evento (GeoJSON); bbox si el hull degenera."""
    points = shapely.points(lon, lat)
    hull = shapely.convex_hull(shapely.MultiPoint(points)) if len(points) > 1 else shapely.convex_hull(points[0])
    if hull.geom_type == "Polygon" and hull.area > 0:
        return json.loads(shapely.to_geojson(hull))
    return _bbox_geojson(lat, lon)


def _bbox_geojson(lat: np.ndarray, lon: np.ndarray) -> dict:
    """Bounding box como polígono GeoJSON válido.

    Si el rango es degenerado (evento de un punto o puntos colineales) se
    expande ±1e-4 grados (~11 m) alrededor del centro para que el anillo
    tenga 4 esquinas distintas y la geometría sea válida.
    """
    west, east = float(np.min(lon)), float(np.max(lon))
    south, north = float(np.min(lat)), float(np.max(lat))
    pad = 1e-4
    if west >= east:
        center = (west + east) / 2.0
        west, east = center - pad, center + pad
    if south >= north:
        center = (south + north) / 2.0
        south, north = center - pad, center + pad
    return {
        "type": "Polygon",
        "coordinates": [[
            [west, south], [east, south], [east, north], [west, north], [west, south],
        ]],
    }


def _classify_event(event: dict) -> tuple[str, str]:
    reasons: list[str] = []
    if event["frp_total"] > _FRP_ROJA_MW:
        reasons.append(f"FRP total {event['frp_total']:.1f} MW > 100 MW")
    if event["nocturnas"] >= 1:
        reasons.append("detección activa en paso nocturno")
    if reasons:
        return "alerta_roja", " | ".join(reasons)
    if event["frp_total"] >= _FRP_MEDIA_MW or event["puntos_count"] >= 3 or len(event["dias"]) > 1:
        reasons.append(
            f"FRP total moderado ({event['frp_total']:.1f} MW) en grupo de {event['puntos_count']} detección(es)"
        )
        return "alerta_media", " | ".join(reasons)
    reasons.append(
        f"punto(s) individuales de bajo FRP ({event['frp_total']:.1f} MW), diurno(s)"
    )
    return "quema_menor", " | ".join(reasons)


def detect_fire_events(
    df_detections: pd.DataFrame,
    *,
    eps_km: float = DEFAULT_EPS_KM,
    eps_days: int = DEFAULT_EPS_DAYS,
    min_points: int = 1,
    flare_radius_km: float = DEFAULT_FLARE_RADIUS_KM,
    flare_sources: list[dict] | None = None,
    geometry_mode: str = "hull",
) -> list[dict]:
    """Agrupa detecciones FIRMS en eventos de incendio y clasifica su alerta.

    Parámetros:
        df_detections: detecciones con ``latitude``, ``longitude``, ``frp``,
            ``daynight`` y fecha de adquisición (``acq_date_local``/``acq_date``).
        eps_km: radio espacial del ST-DBSCAN en km (sugerido 1.5-2).
        eps_days: ventana temporal en días (1 = 24 h, 2 = 48 h).
        min_points: núcleo mínimo del DBSCAN (1 conserva puntos individuales
            como quemas menores).
        flare_radius_km: tolerancia alrededor de cada mechero para excluir
            falsos positivos industriales.
        flare_sources: lista ``[{"name", "lat", "lon"}, ...]``; si no se pasa,
            se carga ``data/regions/mecheros_petroleros.json`` o la lista por defecto.

    Devuelve una lista de eventos ordenada por FRP total descendente.
    """
    df = df_detections.reset_index(drop=True)
    if df.empty:
        return []

    lat = pd.to_numeric(df.get("latitude"), errors="coerce").fillna(0.0).to_numpy()
    lon = pd.to_numeric(df.get("longitude"), errors="coerce").fillna(0.0).to_numpy()
    frp = pd.to_numeric(df.get("frp"), errors="coerce").fillna(0.0).to_numpy() if "frp" in df else np.zeros(len(df))
    daynight = df["daynight"].astype(str).str.upper().to_numpy() if "daynight" in df else np.full(len(df), "", dtype=object)
    thermal = _thermal_contrast(df).to_numpy()
    dates = pd.to_datetime(_date_column(df), errors="coerce")
    day_ord = dates.map(lambda value: value.toordinal() if pd.notna(value) else -10_000).to_numpy().astype(np.int64)
    # Se consumen estos valores por evento. Prepararlos una sola vez evita
    # miles de operaciones pandas cuando el período contiene muchos focos.
    date_labels = dates.dt.strftime("%Y-%m-%d").fillna("").to_numpy()
    point_id_values = df["id"].astype(str).to_numpy() if "id" in df else np.arange(len(df)).astype(str)
    sensor_values = df["sensor"].astype(str).to_numpy() if "sensor" in df else np.full(len(df), "", dtype=object)
    province_values = df["province_id"].astype(str).to_numpy() if "province_id" in df else np.full(len(df), "", dtype=object)

    sources = flare_sources if flare_sources is not None else load_flare_sources()
    flare_mask = _flare_mask(lat, lon, sources, flare_radius_km)

    active_idx = np.flatnonzero(~flare_mask)
    labels = np.full(len(df), -1, dtype=np.int64)
    if active_idx.size:
        labels[active_idx] = _dbscan_st(
            lat[active_idx], lon[active_idx], day_ord[active_idx],
            eps_km=eps_km, eps_days=eps_days, min_points=min_points,
        )

    events: list[dict] = []
    for cluster_id in sorted(set(labels.tolist())):
        if cluster_id < 0:
            continue
        members = np.flatnonzero(labels == cluster_id)
        m_lat, m_lon, m_frp = lat[members], lon[members], frp[members]
        member_dates = date_labels[members]
        valid_dates = member_dates[member_dates != ""]
        start = str(valid_dates.min()) if valid_dates.size else None
        end = str(valid_dates.max()) if valid_dates.size else None
        days = sorted(set(valid_dates.tolist()))
        point_ids = point_id_values[members].tolist()
        # El ID no puede depender del orden del DataFrame ni de la paginación:
        # un mismo conjunto de detecciones debe poder consultarse por detalle
        # después de haber sido listado con filtros.
        event_id = sha1("|".join(sorted(point_ids)).encode("utf-8")).hexdigest()[:12]
        event = {
            "id_evento": f"EVT-{event_id}",
            "frp_total": float(np.sum(m_frp)),
            "frp_max": float(np.max(m_frp)),
            "puntos_count": int(members.size),
        # El feed y las alertas sólo usan centro y miembros. Evitar miles de
        # hulls de Shapely mantiene esa consulta interactiva; los endpoints
        # GeoJSON conservan el hull preciso por defecto.
        "geometria": _bbox_geojson(m_lat, m_lon) if geometry_mode == "bbox" else _convex_hull_geojson(m_lat, m_lon),
            "centro": [float(m_lat.mean()), float(m_lon.mean())],
            "inicio": start,
            "fin": end,
            "dias": days,
            "diurnas": int(np.sum(daynight[members] == "D")),
            "nocturnas": int(np.sum(daynight[members] == "N")),
            "sensores": sorted(set(sensor_values[members])),
            "provincias": sorted(set(province_values[members])),
            "puntos_ids": point_ids,
            "frp_medio": float(np.mean(m_frp)),
            "contraste_medio_k": float(np.mean(thermal[members])),
        }
        level, reason = _classify_event(event)
        event["nivel_alerta"] = level
        event["nivel_alerta_label"] = _ALERT_LABELS[level]
        event["motivo_regla"] = reason
        events.append(event)

    events.sort(key=lambda item: (-item["frp_total"], -item["puntos_count"]))
    for order, event in enumerate(events, start=1):
        event["rank"] = order
    return events
