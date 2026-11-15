"""Entrena los modelos de riesgo por horizonte (0 a 7 días).

Ejemplos:
    python scripts/train_fire_risk_model.py
    python scripts/train_fire_risk_model.py --horizons 0,1,3,7 --quick
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

from app.ml.training import train  # noqa: E402


def _parse_horizons(value: str) -> list[int]:
    horizons = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        horizon = int(part)
        if horizon < 0 or horizon > 7:
            raise argparse.ArgumentTypeError("Los horizontes deben estar entre 0 y 7")
        horizons.append(horizon)
    return sorted(set(horizons))


def main() -> int:
    parser = argparse.ArgumentParser(description="Entrena el modelo de riesgo de incendios de FuegoClaro")
    parser.add_argument("--dataset", type=Path, default=ROOT / "data" / "processed" / "ml" / "fire_risk_dataset.parquet")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data" / "processed" / "ml")
    parser.add_argument("--horizons", type=_parse_horizons, default=list(range(8)), help="Horizontes separados por coma (0..7)")
    parser.add_argument(
        "--negative-ratio",
        type=float,
        default=None,
        help="Negativos por positivo en entrenamiento (default: 5 para h<=1, 3 para h 2-4, 2 para h 5-7)",
    )
    parser.add_argument("--quick", action="store_true", help="Muestra reducida para probar el pipeline")
    parser.add_argument("--skip-importance", action="store_true", help="No calcular importancia por permutación")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    result = train(
        args.dataset,
        args.output_dir,
        horizons=args.horizons,
        negative_ratio=args.negative_ratio,
        quick=args.quick,
        importance=not args.skip_importance,
        random_state=args.seed,
    )
    print(json.dumps(
        {
            "version": result["version"],
            "horizons": result["horizons"],
            "thresholds": {str(key): value for key, value in result["thresholds"].items()},
            "test_metrics": {
                str(key): value.get("test") for key, value in result["metrics"].items()
            },
        },
        indent=2,
        ensure_ascii=False,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
