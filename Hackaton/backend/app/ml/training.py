"""Entrenamiento, calibración y evaluación de los modelos de riesgo.

Un modelo por horizonte ``h = 0..7``. ``h=0`` responde al riesgo del mismo día;
``h=7`` al riesgo de los próximos 7 días (incluyendo el día consultado).

La calibración se hace sobre validación con isotónica (o logística si hay
pocos positivos) y los umbrales Bajo/Medio/Alto/Extremo se fijan con los
percentiles p50/p85/p95 de las probabilidades calibradas de validación.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

LABEL_COLUMNS = [f"y_d{h}" for h in range(8)] + [f"y_within_{h}" for h in range(8)]
BASE_LEAKY_COLUMNS = {
    "det_count",
    "frp_sum",
    "frp_max",
    "frp_mean",
    "night_count",
    "high_conf_count",
    "modis_count",
    "viirs_count",
    "mean_hour",
    "event_count",
    "event_det_count",
    "event_frp_sum",
    "event_frp_max",
    "event_points_max",
    "event_alert_max",
    "event_night_count",
    "fire_day",
}
EXCLUDED_COLUMNS = {
    "date",
    "cell_id",
    "province",
    "province_id",
    "region",
    "region_id",
    "lat_idx",
    "lon_idx",
    "year",
    *LABEL_COLUMNS,
    *BASE_LEAKY_COLUMNS,
}
TRAIN_END = pd.Timestamp("2024-12-31")
VAL_START = pd.Timestamp("2025-01-01")
VAL_END = pd.Timestamp("2025-12-31")
TEST_START = pd.Timestamp("2026-01-01")


class ProbabilityCalibrator:
    """Envoltorio serializable con probabilidad calibrada."""

    def __init__(self, model, calibrator, kind: str) -> None:
        self.model = model
        self.calibrator = calibrator
        self.kind = kind

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        raw = self.model.predict_proba(features)[:, 1]
        if self.kind == "isotonic":
            calibrated = self.calibrator.predict(raw)
        elif self.kind == "sigmoid":
            logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1 - raw, 1e-6, 1))
            calibrated = self.calibrator.predict_proba(logits.reshape(-1, 1))[:, 1]
        else:
            calibrated = raw
        calibrated = np.clip(calibrated, 0.0, 1.0)
        return np.column_stack([1.0 - calibrated, calibrated])


def feature_columns(dataset: pd.DataFrame, horizon: int) -> list[str]:
    columns: list[str] = []
    for column in dataset.columns:
        if column in EXCLUDED_COLUMNS:
            continue
        if column.startswith("y_"):
            continue
        # NDVI crudo del mismo día: solo se permiten sus versiones con lag.
        if column in {"ndvi_value", "ndvi_quality_value", "ndvi_age_value"}:
            continue
        # Clima crudo del mismo día: se usa solo la versión ``_d0`` en h=0.
        if column.startswith("wx_") and not column.endswith(("_d0", "_lag1", "_roll7", "_roll30")):
            continue
        # ``event_count`` y el nivel de alerta se calculan con el evento completo,
        # que puede extenderse al futuro; se conservan para auditoría, no como feature.
        if column == "event_count" or column.startswith(("event_count_", "event_alert_max")):
            continue
        if horizon >= 1 and (column.endswith("_d0") or column == "weather_completeness"):
            continue
        if not pd.api.types.is_numeric_dtype(dataset[column]):
            continue
        columns.append(column)
    return columns


def temporal_split(dataset: pd.DataFrame, horizon: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = pd.to_datetime(dataset["date"])
    train = dataset[dates <= TRAIN_END - pd.Timedelta(days=horizon)]
    validation = dataset[(dates >= VAL_START) & (dates <= VAL_END - pd.Timedelta(days=horizon))]
    test = dataset[(dates >= TEST_START) & (dates <= dates.max() - pd.Timedelta(days=horizon))]
    return train, validation, test


def _positive_label(frame: pd.DataFrame, horizon: int) -> np.ndarray:
    return pd.to_numeric(frame[f"y_within_{horizon}"], errors="coerce").fillna(0).to_numpy(dtype=int)


def _downsample_negatives(
    features: np.ndarray,
    labels: np.ndarray,
    ratio: float,
    *,
    random_state: int = 42,
) -> tuple[np.ndarray, np.ndarray]:
    positives = np.flatnonzero(labels == 1)
    negatives = np.flatnonzero(labels == 0)
    if len(positives) == 0 or len(negatives) == 0:
        return features, labels
    maximum = int(len(positives) * ratio)
    if len(negatives) > maximum:
        rng = np.random.default_rng(random_state)
        negatives = rng.choice(negatives, size=maximum, replace=False)
    keep = np.concatenate([positives, negatives])
    keep.sort()
    return features[keep], labels[keep]


def _sample_weights(labels: np.ndarray) -> np.ndarray:
    positives = max(int((labels == 1).sum()), 1)
    negatives = max(int((labels == 0).sum()), 1)
    scale = negatives / positives
    return np.where(labels == 1, scale, 1.0)


def _fit_calibrator(model, validation: pd.DataFrame, features: list[str], horizon: int) -> ProbabilityCalibrator:
    x_val = validation[features].to_numpy(dtype=np.float32, copy=False)
    y_val = _positive_label(validation, horizon)
    raw = model.predict_proba(x_val)[:, 1]
    positives = int(y_val.sum())
    if positives == 0 or positives == len(y_val) or np.allclose(raw, raw[0]):
        # Sin señal suficiente para calibrar: se conserva la probabilidad base.
        return ProbabilityCalibrator(model, None, "identity")
    if positives >= 200:
        calibrator = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        calibrator.fit(raw, y_val)
        kind = "isotonic"
    else:
        logits = np.log(np.clip(raw, 1e-6, 1 - 1e-6) / np.clip(1 - raw, 1e-6, 1))
        calibrator = LogisticRegression(max_iter=1000, solver="lbfgs")
        calibrator.fit(logits.reshape(-1, 1), y_val)
        kind = "sigmoid"
    return ProbabilityCalibrator(model, calibrator, kind)


def _metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    labels = np.asarray(labels, dtype=int)
    probabilities = np.asarray(probabilities, dtype=float)
    positives = int(labels.sum())
    result: dict[str, float | int | None] = {
        "rows": int(len(labels)),
        "positives": positives,
        "base_rate": float(labels.mean()) if len(labels) else None,
    }
    if positives == 0 or positives == len(labels):
        result.update({"roc_auc": None, "pr_auc": None, "brier": None, "log_loss": None})
        return result
    result["roc_auc"] = float(roc_auc_score(labels, probabilities))
    result["pr_auc"] = float(average_precision_score(labels, probabilities))
    result["brier"] = float(brier_score_loss(labels, probabilities))
    result["log_loss"] = float(log_loss(labels, np.clip(probabilities, 1e-9, 1 - 1e-9)))
    for threshold in (0.1, 0.2, 0.3, 0.5):
        prediction = (probabilities >= threshold).astype(int)
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, prediction, average="binary", zero_division=0
        )
        result[f"precision_at_{threshold}"] = float(precision)
        result[f"recall_at_{threshold}"] = float(recall)
        result[f"f1_at_{threshold}"] = float(f1)
    order = np.argsort(-probabilities)
    for fraction in (0.01, 0.05, 0.10):
        top = max(1, int(len(labels) * fraction))
        selected = order[:top]
        result[f"precision_top_{int(fraction * 100)}pct"] = float(labels[selected].mean())
        result[f"capture_top_{int(fraction * 100)}pct"] = float(labels[selected].sum() / positives)
    return result


def risk_levels(probabilities: np.ndarray, thresholds: dict) -> np.ndarray:
    values = np.asarray(probabilities, dtype=float)
    levels = np.full(len(values), "Bajo", dtype=object)
    levels[values > thresholds["q50"]] = "Medio"
    levels[values > thresholds["q85"]] = "Alto"
    levels[values > thresholds["q95"]] = "Extremo"
    return levels


def _validation_thresholds(probabilities: np.ndarray) -> dict:
    values = np.asarray(probabilities, dtype=float)
    return {
        "q50": float(np.quantile(values, 0.50)),
        "q85": float(np.quantile(values, 0.85)),
        "q95": float(np.quantile(values, 0.95)),
        "method": "percentiles de validación (p50/p85/p95)",
    }


def train(
    dataset_path: Path,
    output_dir: Path,
    *,
    horizons: list[int] | None = None,
    negative_ratio: float | None = None,
    quick: bool = False,
    importance: bool = True,
    random_state: int = 42,
) -> dict:
    """Entrena todos los horizontes y guarda ``risk_model.joblib``."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    dataset = pd.read_parquet(dataset_path)
    dataset["date"] = pd.to_datetime(dataset["date"]).dt.normalize()
    if quick:
        dataset = dataset.sample(min(200_000, len(dataset)), random_state=random_state).sort_values("date")
    horizons = horizons or list(range(8))
    output_dir.mkdir(parents=True, exist_ok=True)

    bundle: dict = {
        "version": f"fuegoclaro-risk-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "horizons": {},
        "feature_columns": {},
        "thresholds": {},
        "metrics": {},
        "calibration": {},
    }
    importance_rows: list[dict] = []

    for horizon in horizons:
        logger.info("Horizonte h=%s", horizon)
        train_frame, validation_frame, test_frame = temporal_split(dataset, horizon)
        train_frame = train_frame.dropna(subset=[f"y_within_{horizon}"])
        validation_frame = validation_frame.dropna(subset=[f"y_within_{horizon}"])
        test_frame = test_frame.dropna(subset=[f"y_within_{horizon}"])
        if train_frame.empty or validation_frame.empty:
            logger.warning("Horizonte %s sin datos suficientes; se omite", horizon)
            continue

        features = feature_columns(dataset, horizon)
        # Elimina columnas constantes o totalmente vacías en entrenamiento.
        features = [
            column
            for column in features
            if train_frame[column].notna().any() and train_frame[column].nunique(dropna=True) > 1
        ]
        if not features:
            logger.warning("Horizonte %s sin variables útiles; se omite", horizon)
            continue
        x_train = train_frame[features].to_numpy(dtype=np.float32, copy=False)
        y_train = _positive_label(train_frame, horizon)
        ratio = negative_ratio
        if ratio is None:
            ratio = 5.0 if horizon <= 1 else 3.0 if horizon <= 4 else 2.0
        x_train, y_train = _downsample_negatives(
            x_train, y_train, ratio, random_state=random_state
        )
        weights = _sample_weights(y_train)
        logger.info(
            "  train=%s (pos=%s) val=%s test=%s features=%s",
            len(y_train),
            int(y_train.sum()),
            len(validation_frame),
            len(test_frame),
            len(features),
        )

        model = HistGradientBoostingClassifier(
            max_iter=300,
            learning_rate=0.05,
            max_leaf_nodes=31,
            min_samples_leaf=40,
            l2_regularization=1.0,
            early_stopping=False,
            random_state=random_state,
        )
        model.fit(x_train, y_train, sample_weight=weights)
        calibrated = _fit_calibrator(model, validation_frame, features, horizon)

        validation_probabilities = calibrated.predict_proba(
            validation_frame[features].to_numpy(dtype=np.float32, copy=False)
        )[:, 1]
        thresholds = _validation_thresholds(validation_probabilities)

        test_probabilities = (
            calibrated.predict_proba(test_frame[features].to_numpy(dtype=np.float32, copy=False))[:, 1]
            if not test_frame.empty
            else np.array([])
        )
        test_metrics = _metrics(_positive_label(test_frame, horizon), test_probabilities) if not test_frame.empty else {}
        validation_metrics = _metrics(_positive_label(validation_frame, horizon), validation_probabilities)

        # Baselines: frecuencia histórica de la celda y persistencia de FIRMS.
        baselines: dict[str, dict] = {}
        if not test_frame.empty:
            labels = _positive_label(test_frame, horizon)
            if "fire_freq_cell" in test_frame:
                baselines["climatologia_celda"] = _metrics(labels, test_frame["fire_freq_cell"].fillna(0).to_numpy())
            if "det_count_lag1" in test_frame:
                baselines["persistencia_firms"] = _metrics(
                    labels, (test_frame["det_count_lag1"].fillna(0).to_numpy() > 0).astype(float)
                )
            try:
                x_base, y_base = x_train, y_train
                if len(y_base) > 150_000:
                    rng = np.random.default_rng(random_state)
                    keep = rng.choice(len(y_base), size=150_000, replace=False)
                    x_base, y_base = x_base[keep], y_base[keep]
                logistic = make_pipeline(
                    SimpleImputer(strategy="median"),
                    StandardScaler(),
                    LogisticRegression(max_iter=300, class_weight="balanced", random_state=random_state),
                )
                logistic.fit(x_base, y_base)
                baselines["regresion_logistica"] = _metrics(
                    labels,
                    logistic.predict_proba(
                        test_frame[features].to_numpy(dtype=np.float32, copy=False)
                    )[:, 1],
                )
            except Exception as exc:  # noqa: BLE001 - un baseline no debe romper el entrenamiento
                logger.warning("Baseline logístico omitido: %s", exc)

        if importance and len(test_frame):
            sample = test_frame.sample(min(10_000, len(test_frame)), random_state=random_state)
            x_sample = sample[features].to_numpy(dtype=np.float32, copy=False)
            y_sample = _positive_label(sample, horizon)
            if len(np.unique(y_sample)) > 1:
                result = permutation_importance(
                    calibrated.model,
                    x_sample,
                    y_sample,
                    scoring="average_precision",
                    n_repeats=3,
                    random_state=random_state,
                    n_jobs=-1,
                )
                for position in np.argsort(-result.importances_mean)[:25]:
                    importance_rows.append(
                        {
                            "horizon": horizon,
                            "feature": features[position],
                            "importance_mean": float(result.importances_mean[position]),
                            "importance_std": float(result.importances_std[position]),
                        }
                    )

        bundle["horizons"][horizon] = calibrated
        bundle["feature_columns"][horizon] = features
        bundle["thresholds"][horizon] = thresholds
        bundle["metrics"][horizon] = {
            "validation": validation_metrics,
            "test": test_metrics,
            "baselines": baselines,
        }
        bundle["calibration"][horizon] = calibrated.kind

    if not bundle["horizons"]:
        raise RuntimeError(
            "No se entrenó ningún horizonte: el dataset no cubre los periodos de "
            "entrenamiento/validación. Revisa --start/--end y las fechas del dataset."
        )
    joblib.dump(bundle, output_dir / "risk_model.joblib")
    (output_dir / "risk_model_metrics.json").write_text(
        json.dumps(
            {
                "version": bundle["version"],
                "trained_at": bundle["trained_at"],
                "horizons": {str(key): value for key, value in bundle["metrics"].items()},
                "thresholds": {str(key): value for key, value in bundle["thresholds"].items()},
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (output_dir / "risk_thresholds.json").write_text(
        json.dumps({str(key): value for key, value in bundle["thresholds"].items()}, indent=2),
        encoding="utf-8",
    )
    (output_dir / "risk_feature_columns.json").write_text(
        json.dumps({str(key): value for key, value in bundle["feature_columns"].items()}, indent=2),
        encoding="utf-8",
    )
    if importance_rows:
        pd.DataFrame(importance_rows).to_csv(output_dir / "risk_feature_importance.csv", index=False)
    logger.info("Modelo guardado en %s", output_dir / "risk_model.joblib")
    return {
        "version": bundle["version"],
        "horizons": list(bundle["horizons"].keys()),
        "metrics": bundle["metrics"],
        "thresholds": bundle["thresholds"],
    }
