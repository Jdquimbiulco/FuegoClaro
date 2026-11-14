#!/usr/bin/env python3
"""Construye las geometrías provinciales de Ecuador usadas para asignar regiones.

Fuente: Natural Earth 1:10m Admin 1 – States/Provinces (dominio público).
Uso:
    backend/.venv/bin/python scripts/build_regions.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
from shapely.geometry import mapping, shape
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.domain.models import PROVINCES, NATURAL_REGIONS  # noqa: E402

SOURCE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_1_states_provinces.geojson"
)
OUTPUT = ROOT / "data" / "regions" / "ecuador_provinces.geojson"


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    print("Descargando Natural Earth admin-1...")
    response = httpx.get(SOURCE_URL, timeout=120, follow_redirects=True)
    response.raise_for_status()
    collection = response.json()

    features = []
    for feature in collection.get("features", []):
        props = feature.get("properties", {})
        if props.get("adm0_a3") != "ECU" and props.get("iso_a2") != "EC":
            continue
        iso = props.get("iso_3166_2") or ""
        if iso not in PROVINCES:
            print(f"  ! provincia sin mapeo ISO: {props.get('name')} ({iso})")
            continue
        canonical_name, natural_id = PROVINCES[iso]
        geometry = shape(feature["geometry"])
        if not geometry.is_valid:
            geometry = geometry.buffer(0)
        # Simplificación suave: precisión suficiente para asignar puntos y dibujar.
        simplified = orient(geometry.simplify(0.005, preserve_topology=True), sign=1.0)
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "iso_3166_2": iso,
                    "name": canonical_name,
                    "region_id": natural_id,
                    "region": NATURAL_REGIONS[natural_id]["name"],
                },
                "geometry": mapping(simplified),
            }
        )

    payload = {"type": "FeatureCollection", "name": "Ecuador provinces (Natural Earth, simplified)", "features": features}
    with OUTPUT.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(features)} provincias -> {OUTPUT} ({OUTPUT.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
