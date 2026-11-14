#!/usr/bin/env python3
"""Descarga y procesa focos de calor de NASA FIRMS para Ecuador.

Ejemplos:
    backend/.venv/bin/python scripts/ingest_firms.py --start 2024-01-01 --end 2024-12-31
    backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12

La clave FIRMS se lee de backend/.env (FIRMS_MAP_KEY). No se escribe en el dataset.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.logging import configure_logging  # noqa: E402
from app.domain.models import DEFAULT_END_DATE, DEFAULT_START_DATE, ECUADOR_BBOX  # noqa: E402
from app.services.ingestion import ingest  # noqa: E402
from app.utils.time import today_utc  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingesta de focos de calor NASA FIRMS para Ecuador")
    parser.add_argument("--start", default=DEFAULT_START_DATE, help="Fecha inicial YYYY-MM-DD")
    parser.add_argument("--end", default=min(DEFAULT_END_DATE, today_utc().isoformat()), help="Fecha final YYYY-MM-DD")
    parser.add_argument("--keep-raw", action="store_true", help="Guardar CSV crudos en data/raw/")
    parser.add_argument("--no-sample", action="store_true", help="No generar muestra offline")
    parser.add_argument("--bbox", default=",".join(str(v) for v in ECUADOR_BBOX), help="west,south,east,north")
    args = parser.parse_args()

    configure_logging(logging.INFO)
    from app.utils.time import parse_iso_date

    start = parse_iso_date(args.start, "fecha inicial")
    end = parse_iso_date(args.end, "fecha final")
    bbox = tuple(float(value) for value in args.bbox.split(","))
    if len(bbox) != 4:
        raise SystemExit("El bbox debe tener 4 valores: west,south,east,north")

    manifest = ingest(start, end, bbox=bbox, keep_raw=args.keep_raw, make_sample=not args.no_sample)
    print("\nResumen de ingesta")
    print(f"  Dataset : {manifest['dataset_version']}")
    print(f"  Periodo : {manifest['date_range']['start']} .. {manifest['date_range']['end']}")
    print(f"  Registros: {manifest['records']['final']:,}")
    print(f"  Sensores : {manifest['records']['by_sensor']}")
    print(f"  Regiones : {manifest['records']['by_region']}")


if __name__ == "__main__":
    main()
