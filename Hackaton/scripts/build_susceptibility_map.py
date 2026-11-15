"""Genera las capas GeoJSON de susceptibilidad para el mapa web.

Por defecto produce los horizontes 0, 1, 3 y 7. El archivo ``latest-h7`` es
además el respaldo del contrato histórico ``data/processed/susceptibility.json``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.ml.inference import FireRiskPredictor  # noqa: E402


def parse_horizons(value: str) -> list[int]:
    horizons = sorted({int(item.strip()) for item in value.split(",") if item.strip()})
    if not horizons or any(item < 0 or item > 7 for item in horizons):
        raise argparse.ArgumentTypeError("Los horizontes deben estar entre 0 y 7.")
    return horizons


def cell_geometry(lat: float, lon: float, step: float = 0.1) -> dict:
    half = step / 2
    return {
        "type": "Polygon",
        "coordinates": [[[lon - half, lat - half], [lon + half, lat - half], [lon + half, lat + half], [lon - half, lat + half], [lon - half, lat - half]]],
    }


def build_collection(predictor: FireRiskPredictor, target_date: str, horizon: int) -> dict:
    frame = predictor.predict_grid(target_date, window_days=horizon)
    counts = frame["risk_level"].value_counts().to_dict()
    features = []
    for row in frame.itertuples(index=False):
        features.append(
            {
                "type": "Feature",
                "geometry": cell_geometry(float(row.lat), float(row.lon)),
                "properties": {
                    "area_id": str(row.cell_id),
                    "level": "cell",
                    "latitude": round(float(row.lat), 5),
                    "longitude": round(float(row.lon), 5),
                    "province": str(row.province),
                    "province_id": str(row.province_id),
                    "region": str(row.region),
                    "region_id": str(row.region_id),
                    "is_galapagos": bool(row.is_galapagos),
                    "probability": round(float(row.probability), 6),
                    "risk_level": str(row.risk_level),
                    "data_completeness": round(float(row.data_completeness), 4),
                    "prediction_date": str(row.prediction_date),
                    "window_days": int(row.window_days),
                    "model_version": row.model_version,
                },
            }
        )
    thresholds = predictor.bundle["thresholds"][horizon]
    return {
        "type": "FeatureCollection",
        "features": features,
        "model": {
            "name": "HistGradientBoostingClassifier",
            "version": predictor.bundle.get("version"),
            "trained_at": predictor.bundle.get("trained_at"),
            "window_days": horizon,
            "prediction_date": target_date,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "risk_bands": [
            {"level": "Bajo", "max": thresholds["q50"]},
            {"level": "Medio", "min": thresholds["q50"], "max": thresholds["q85"]},
            {"level": "Alto", "min": thresholds["q85"], "max": thresholds["q95"]},
            {"level": "Extremo", "min": thresholds["q95"]},
        ],
        "summary": {
            "areas_total": len(features),
            "areas_in_scope": len(features),
            "by_risk": {level: int(counts.get(level, 0)) for level in ("Bajo", "Medio", "Alto", "Extremo")},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "notes": [
            "Cada polígono representa una celda de 0.1° (~11 km), no un incendio confirmado.",
            "Los niveles son relativos a los umbrales de validación del horizonte seleccionado.",
            "Galápagos se muestra con advertencia: su actividad volcánica puede producir anomalías térmicas.",
        ],
    }


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Genera GeoJSON de susceptibilidad para el mapa")
    parser.add_argument("--date", default=datetime.now(ZoneInfo("America/Guayaquil")).date().isoformat(), help="Fecha base YYYY-MM-DD")
    parser.add_argument("--horizons", type=parse_horizons, default=parse_horizons(settings.susceptibility_horizons))
    parser.add_argument("--output-dir", type=Path, default=settings.susceptibility_dir)
    args = parser.parse_args()

    predictor = FireRiskPredictor()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for horizon in args.horizons:
        payload = build_collection(predictor, args.date, horizon)
        path = args.output_dir / f"latest-h{horizon}.geojson"
        path.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"Generado {path} ({len(payload['features'])} celdas)")
        if horizon == 7:
            legacy = settings.processed_dir / "susceptibility.json"
            shutil.copyfile(path, legacy)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
