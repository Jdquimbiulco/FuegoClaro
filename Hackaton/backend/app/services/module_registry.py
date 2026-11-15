"""Registro perezoso de módulos opcionales y sus artefactos."""

from __future__ import annotations

import threading
from dataclasses import dataclass

from app.core.config import get_settings
from app.core.errors import ModuleContractError, ModuleNotReadyError


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    status: str
    version: str | None
    artifact: str | None
    detail: str | None = None


_predictor = None
_predictor_lock = threading.Lock()


def predictor_artifacts_present() -> bool:
    folder = get_settings().ml_dir
    return (folder / "risk_model.joblib").exists() and (folder / "fire_risk_dataset.parquet").exists()


def _missing_predictor_detail() -> str:
    folder = get_settings().ml_dir
    missing = [name for name in ("risk_model.joblib", "fire_risk_dataset.parquet") if not (folder / name).exists()]
    return f"Faltan artefactos: {', '.join(missing)}." if missing else "No se pudo cargar el predictor."


def get_fire_risk_predictor():
    """Carga el predictor una sola vez, solo al solicitar una inferencia."""
    global _predictor
    if _predictor is not None:
        return _predictor
    with _predictor_lock:
        if _predictor is not None:
            return _predictor
        if not predictor_artifacts_present():
            raise ModuleNotReadyError("susceptibility", _missing_predictor_detail())
        try:
            from app.ml.inference import FireRiskPredictor

            _predictor = FireRiskPredictor()
            return _predictor
        except ModuleNotReadyError:
            raise
        except FileNotFoundError as exc:
            raise ModuleNotReadyError("susceptibility", str(exc)) from exc
        except Exception as exc:  # el backend no debe quedar inconsistente por un bundle corrupto
            raise ModuleContractError("susceptibility", str(exc)) from exc


def predictor_info() -> ModuleInfo:
    if not predictor_artifacts_present():
        return ModuleInfo("susceptibility", "pending", None, None, _missing_predictor_detail())
    try:
        predictor = get_fire_risk_predictor()
        return ModuleInfo(
            "susceptibility",
            "available",
            str(predictor.bundle.get("version")) if predictor.bundle.get("version") else None,
            str(predictor.model_path),
        )
    except ModuleContractError as exc:
        return ModuleInfo("susceptibility", "error", None, None, exc.details.get("detail"))
