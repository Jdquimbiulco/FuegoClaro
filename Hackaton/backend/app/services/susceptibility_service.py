"""Acceso al mapa agregado y a la inferencia puntual de riesgo."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import InputValidationError, ModuleContractError
from app.domain.dtos import PointRiskDTO, SusceptibilityMapDTO
from app.domain.models import ECUADOR_BBOX
from app.services.module_registry import ModuleInfo, get_fire_risk_predictor, predictor_info

_map_cache: dict[Path, tuple[float, dict]] = {}


def module_info() -> ModuleInfo:
    return predictor_info()


def _empty_map(level: str, window_days: int) -> SusceptibilityMapDTO:
    return SusceptibilityMapDTO(
        level=level,
        features=[],
        model={"name": "HistGradientBoostingClassifier", "version": None, "trained_at": None, "window_days": window_days, "metrics": {}},
        risk_bands=[],
        summary={"areas_total": 0, "areas_in_scope": 24, "by_risk": {"Bajo": 0, "Medio": 0, "Alto": 0, "Extremo": 0}, "generated_at": None},
        notes=["El mapa agregado aún no se generó. Usa /api/v1/susceptibility/point para consultas puntuales cuando el modelo esté disponible."],
    )


def _load_map(path: Path) -> dict:
    mtime = path.stat().st_mtime
    cached = _map_cache.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModuleContractError("susceptibility", f"No se puede leer susceptibility.json: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ModuleContractError("susceptibility", "susceptibility.json debe ser un FeatureCollection GeoJSON.")
    _map_cache[path] = (mtime, payload)
    return payload


def _map_path(window_days: int) -> Path:
    settings = get_settings()
    folder = getattr(settings, "susceptibility_dir", settings.processed_dir / "susceptibility")
    candidate = folder / f"latest-h{window_days}.geojson"
    if candidate.exists():
        return candidate
    # Compatibilidad con el primer artefacto h=7 de la API.
    return settings.processed_dir / "susceptibility.json" if window_days == 7 else candidate


def get_map(*, level: str = "province", region_id: str | None = None, window_days: int = 7) -> SusceptibilityMapDTO:
    if level not in {"cell", "province", "canton"}:
        raise InputValidationError("level debe ser cell, province o canton", {"level": level})
    if not 0 <= window_days <= 7:
        raise InputValidationError("window_days debe estar entre 0 y 7.", {"window_days": window_days})
    path = _map_path(window_days)
    if not path.exists():
        return _empty_map(level, window_days)
    payload = _load_map(path)
    features = payload["features"]
    if region_id:
        features = [
            feature for feature in features
            if feature.get("properties", {}).get("region_id") == region_id
            or feature.get("properties", {}).get("area_id") == region_id
        ]
    if level:
        features = [feature for feature in features if feature.get("properties", {}).get("level", level) == level]
    return SusceptibilityMapDTO(
        level=level,
        type="FeatureCollection",
        features=features,
        model=payload.get("model", {}),
        risk_bands=payload.get("risk_bands", []),
        summary=payload.get("summary", {}),
        notes=payload.get("notes", ["El mapa agrega probabilidades de celdas; no es una predicción provincial independiente."]),
    )


def predict_point(*, latitude: float, longitude: float, when: str, window_days: int = 7) -> PointRiskDTO:
    west, south, east, north = ECUADOR_BBOX
    if not south <= latitude <= north or not west <= longitude <= east:
        raise InputValidationError(
            "La coordenada debe estar dentro del BBox de Ecuador.",
            {"lat": latitude, "lon": longitude, "bbox": [west, south, east, north]},
        )
    if not 0 <= window_days <= 7:
        raise InputValidationError("window_days debe estar entre 0 y 7.", {"window_days": window_days})
    try:
        date.fromisoformat(when)
    except ValueError as exc:
        raise InputValidationError("date debe tener formato YYYY-MM-DD.", {"date": when}) from exc
    try:
        result = get_fire_risk_predictor().predict(latitude, longitude, when, window_days=window_days)
        return PointRiskDTO.model_validate(result)
    except (InputValidationError, ModuleContractError):
        raise
    except ValueError as exc:
        raise InputValidationError(str(exc)) from exc
