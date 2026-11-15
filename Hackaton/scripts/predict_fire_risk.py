"""Predice el nivel de riesgo de incendio para una ubicación y fecha.

Ejemplos:
    python scripts/predict_fire_risk.py --lat -4.4161 --lon -79.54454 --date 2026-11-20
    python scripts/predict_fire_risk.py --lat -0.18 --lon -78.48 --date 2025-09-01 --window-days 0
    python scripts/predict_fire_risk.py --batch entradas.csv --output salidas.csv
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

from app.ml.inference import FireRiskPredictor, predict_batch  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Predice riesgo de incendio por ubicación y fecha")
    parser.add_argument("--lat", type=float, help="Latitud WGS84")
    parser.add_argument("--lon", type=float, help="Longitud WGS84")
    parser.add_argument("--date", help="Fecha local (YYYY-MM-DD)")
    parser.add_argument("--window-days", type=int, default=7, choices=range(0, 8), help="Horizonte 0..7 (0=mismo día)")
    parser.add_argument("--batch", type=Path, help="CSV con columnas latitude,longitude,date[,window_days]")
    parser.add_argument("--output", type=Path, default=None, help="CSV de salida para --batch")
    parser.add_argument("--model", type=Path, default=None, help="Ruta del modelo joblib")
    parser.add_argument("--dataset", type=Path, default=None, help="Ruta del dataset parquet")
    args = parser.parse_args()

    predictor = FireRiskPredictor(model_path=args.model, dataset_path=args.dataset)
    if args.batch:
        if not args.output:
            raise SystemExit("--batch requiere --output")
        result = predict_batch(predictor, args.batch, args.output)
        print(json.dumps({"rows": len(result), "output": str(args.output)}, indent=2))
        return 0

    if args.lat is None or args.lon is None or not args.date:
        raise SystemExit("Indica --lat, --lon y --date, o usa --batch")
    result = predictor.predict(args.lat, args.lon, args.date, window_days=args.window_days)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
