"""Genera el dataset supervisado de riesgo de incendios.

Ejemplos:
    python scripts/build_fire_risk_dataset.py
    python scripts/build_fire_risk_dataset.py --skip-ndvi
    python scripts/build_fire_risk_dataset.py --limit-cells 80 --skip-weather --skip-dem --skip-ndvi
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from app.ml.dataset import build_dataset  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye el dataset de riesgo de incendios de FuegoClaro")
    parser.add_argument("--grid", type=float, default=0.1, help="Tamaño de celda en grados (default 0.1)")
    parser.add_argument("--start", default="2022-01-01", help="Fecha inicial local (YYYY-MM-DD)")
    parser.add_argument("--end", default="2026-11-12", help="Fecha final local (YYYY-MM-DD)")
    parser.add_argument("--detections", type=Path, default=None, help="CSV de detecciones (default data/processed/detections.csv)")
    parser.add_argument("--output-dir", type=Path, default=None, help="Directorio de salida (default data/processed/ml)")
    parser.add_argument("--skip-weather", action="store_true", help="No descargar clima de Open-Meteo")
    parser.add_argument("--skip-dem", action="store_true", help="No descargar DEM")
    parser.add_argument("--skip-ndvi", action="store_true", help="No solicitar NDVI a AppEEARS")
    parser.add_argument("--refresh-weather", action="store_true", help="Ignorar caché de clima/DEM")
    parser.add_argument("--refresh-ndvi", action="store_true", help="Ignorar caché de NDVI")
    parser.add_argument("--refresh-events", action="store_true", help="Volver a ejecutar ST-DBSCAN y no usar eventos cacheados")
    parser.add_argument("--exclude-galapagos", action="store_true", help="Excluir Galápagos del dataset")
    parser.add_argument("--limit-cells", type=int, default=None, help="Limitar celdas (pruebas de humo)")
    parser.add_argument("--weather-chunk", type=int, default=25, help="Celdas por petición a Open-Meteo")
    parser.add_argument("--ndvi-chunk", type=int, default=500, help="Puntos por tarea de AppEEARS")
    parser.add_argument("--ndvi-timeout", type=int, default=7200, help="Segundos máximos de espera por tarea NDVI")
    args = parser.parse_args()

    manifest = build_dataset(
        grid_step=args.grid,
        start=args.start,
        end=args.end,
        detections_path=args.detections,
        output_dir=args.output_dir,
        skip_weather=args.skip_weather,
        skip_dem=args.skip_dem,
        skip_ndvi=args.skip_ndvi,
        refresh_weather=args.refresh_weather,
        refresh_ndvi=args.refresh_ndvi,
        refresh_events=args.refresh_events,
        include_galapagos=not args.exclude_galapagos,
        limit_cells=args.limit_cells,
        weather_chunk=args.weather_chunk,
        ndvi_chunk=args.ndvi_chunk,
        ndvi_timeout=args.ndvi_timeout,
    )
    print(json.dumps(
        {
            "dataset_version": manifest["dataset_version"],
            "rows": manifest["rows"],
            "cells": manifest["cells"],
            "events": manifest["events"],
            "positive_counts": manifest["positive_counts"],
            "warnings": manifest["warnings"],
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
