"""Verificación rápida del dataset procesado de FuegoClaro.

Uso:
    backend/.venv/bin/python scripts/check_dataset.py

No modifica datos. Imprime cobertura por sensor/producto, conteos y
posibles problemas de integridad para revisión antes de una demo.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
CSV_PATH = PROCESSED / "detections.csv"
MANIFEST_PATH = PROCESSED / "manifest.json"

REQUIRED = ["id", "sensor", "source_product", "latitude", "longitude", "acq_date", "acq_time", "acquired_at_utc", "acq_date_local"]


def main() -> int:
    problems: list[str] = []
    if not CSV_PATH.exists():
        print(f"FALTA: {CSV_PATH}")
        return 1
    if not MANIFEST_PATH.exists():
        problems.append(f"Falta el manifiesto: {MANIFEST_PATH}")

    df = pd.read_csv(CSV_PATH, low_memory=False)
    print(f"Archivo: {CSV_PATH} ({CSV_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"Registros: {len(df):,}")

    missing_columns = [column for column in REQUIRED if column not in df.columns]
    if missing_columns:
        problems.append(f"Faltan columnas: {', '.join(missing_columns)}")
    else:
        missing = df[REQUIRED].isna().any(axis=1).sum()
        if missing:
            problems.append(f"Registros con campos obligatorios vacíos: {missing:,}")

    duplicates = int(df["id"].duplicated().sum()) if "id" in df else 0
    if duplicates:
        problems.append(f"IDs duplicados: {duplicates:,}")

    if {"latitude", "longitude"}.issubset(df.columns):
        invalid_coords = (~df["latitude"].between(-90, 90) | ~df["longitude"].between(-180, 180)).sum()
        if invalid_coords:
            problems.append(f"Coordenadas inválidas: {invalid_coords:,}")

    print("\nCobertura por sensor")
    for sensor, group in df.groupby("sensor"):
        print(
            f"  {sensor:6s} {len(group):>7,}  {group['acq_date_local'].min()} .. {group['acq_date_local'].max()}"
        )
        for product, product_group in group.groupby("source_product"):
            print(
                f"         {product:18s} {len(product_group):>7,}  "
                f"{product_group['acq_date_local'].min()} .. {product_group['acq_date_local'].max()}"
            )

    if "acq_date_local" in df:
        dates = pd.to_datetime(df["acq_date_local"], errors="coerce")
        if dates.isna().any():
            problems.append(f"Fechas locales inválidas: {int(dates.isna().sum()):,}")
        else:
            expected = pd.date_range(dates.min(), dates.max(), freq="D")
            missing_days = sorted(set(expected) - set(dates.dt.normalize()))
            if missing_days:
                print(f"\nDías sin ninguna detección: {len(missing_days)} (puede ser normal; no implica ausencia de fuego)")

    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        print("\nManifiesto")
        print(f"  Versión: {manifest.get('dataset_version')}")
        print(f"  Generado: {manifest.get('generated_at')}")
        print(f"  Periodo: {manifest.get('date_range')}")
        records = manifest.get("records", {})
        if records.get("final") and int(records["final"]) != len(df):
            problems.append(
                f"El manifiesto declara {records['final']:,} registros finales, el CSV tiene {len(df):,}."
            )

    print("\nResultado")
    if problems:
        for problem in problems:
            print(f"  ADVERTENCIA: {problem}")
        return 2
    print("  Sin problemas de integridad detectados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
