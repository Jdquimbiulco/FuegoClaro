"""Inferencia del riesgo de incendio para una ubicación y fecha.

Carga el modelo calibrado y el dataset de features generado por
``build_fire_risk_dataset.py``. Para fechas dentro del histórico usa la fila
exacta; para fechas futuras toma el último estado disponible de la celda,
actualiza el calendario y, si es posible, el pronóstico meteorológico del día.
"""

from __future__ import annotations

import json
import logging
from datetime import date as date_type
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.ml.external import OpenMeteoClient, WEATHER_VARIABLES
from app.ml.grid import DEFAULT_GRID_STEP, cell_id, land_cells, nearest_cell
from app.ml.training import risk_levels

logger = logging.getLogger(__name__)

LEVEL_ORDER = ["Bajo", "Medio", "Alto", "Extremo"]


class FireRiskPredictor:
    def __init__(
        self,
        *,
        model_path: Path | None = None,
        dataset_path: Path | None = None,
        static_path: Path | None = None,
        importance_path: Path | None = None,
        grid_step: float = DEFAULT_GRID_STEP,
    ) -> None:
        settings = get_settings()
        folder = settings.ml_dir
        self.model_path = Path(model_path or folder / "risk_model.joblib")
        self.dataset_path = Path(dataset_path or folder / "fire_risk_dataset.parquet")
        self.static_path = Path(static_path or self.dataset_path.parent / "cells_static.parquet")
        self.importance_path = Path(importance_path or self.model_path.parent / "risk_feature_importance.csv")
        if not self.model_path.exists():
            raise FileNotFoundError(
                f"No existe {self.model_path}. Ejecuta scripts/train_fire_risk_model.py primero."
            )
        if not self.dataset_path.exists():
            raise FileNotFoundError(
                f"No existe {self.dataset_path}. Ejecuta scripts/build_fire_risk_dataset.py primero."
            )
        self.bundle = joblib.load(self.model_path)
        self.cells = pd.read_parquet(self.static_path) if self.static_path.exists() else land_cells(step=grid_step)
        self.grid_step = grid_step
        self._cell_ids = set(self.cells["cell_id"].astype(str))
        self.importance = (
            pd.read_csv(self.importance_path) if self.importance_path.exists() else pd.DataFrame()
        )

    # ------------------------------------------------------------------ helpers
    def _resolve_cell(self, latitude: float, longitude: float) -> tuple[str, float, list[str]]:
        warnings: list[str] = []
        lat_idx = int(np.floor(latitude / self.grid_step))
        lon_idx = int(np.floor(longitude / self.grid_step))
        direct = cell_id(lat_idx, lon_idx)
        if direct in self._cell_ids:
            center = self.cells[self.cells["cell_id"].astype(str) == direct].iloc[0]
            distance = float(
                np.hypot(
                    (latitude - float(center["lat"])) * 111.0,
                    (longitude - float(center["lon"])) * 111.0 * np.cos(np.radians(latitude)),
                )
            )
            return direct, distance, warnings
        chosen, distance = nearest_cell(latitude, longitude, self.cells)
        warnings.append(
            f"La coordenada no cae en una celda terrestre con historial; se usó la celda {chosen} a {distance:.1f} km."
        )
        return chosen, distance, warnings

    def _load_row(self, cell: str, when: pd.Timestamp) -> tuple[pd.Series, bool]:
        """Devuelve la fila de features y si es histórica exacta."""
        import pyarrow.parquet as pq
        parquet = pq.ParquetFile(self.dataset_path)
        candidates = []
        for group in range(parquet.num_row_groups):
            keys = parquet.read_row_group(group, columns=["cell_id", "date"], use_threads=False).to_pandas()
            selected = keys.loc[keys["cell_id"] == cell, ["date"]].copy()
            selected["_row"] = selected.index
            selected["_group"] = group
            candidates.append(selected)
            del keys
        history = pd.concat(candidates, ignore_index=True)
        if history.empty:
            raise ValueError(f"No hay historial para la celda {cell}")
        exact_rows = history.loc[history["date"] == when]
        exact = not exact_rows.empty
        if exact:
            selected = exact_rows.iloc[0]
        else:
            history = history.sort_values("date")
            past = history.loc[history["date"] <= when]
            if past.empty:
                raise ValueError(
                    f"La fecha {when.date()} es anterior al inicio del historial de la celda {cell} "
                    f"({history['date'].min().date()})."
                )
            selected = past.iloc[-1]
        # Proyecta pocas columnas a la vez: los grupos tienen un millón de
        # filas y decodificar las 210 columnas simultáneamente agota 512 MiB.
        values = {}
        columns = parquet.schema_arrow.names
        for start in range(0, len(columns), 4):
            table = parquet.read_row_group(int(selected["_group"]), columns=columns[start:start + 4], use_threads=False)
            values.update(table.slice(int(selected["_row"]), 1).to_pandas().iloc[0].to_dict())
            del table
        return pd.Series(values), exact

    def _update_calendar(self, row: pd.Series, when: pd.Timestamp) -> None:
        row["month"] = when.month
        day_of_year = int(when.day_of_year)
        row["day_of_year"] = day_of_year
        row["week_of_year"] = int(when.isocalendar().week)
        row["weekday"] = when.day_of_week
        row["is_weekend"] = int(when.day_of_week >= 5)
        row["doy_sin"] = np.sin(2 * np.pi * day_of_year / 365.25)
        row["doy_cos"] = np.cos(2 * np.pi * day_of_year / 365.25)

    def _update_forecast_weather(self, row: pd.Series, cell: str, when: pd.Timestamp, horizon: int) -> list[str]:
        warnings: list[str] = []
        if horizon >= 1:
            return warnings
        if when < pd.Timestamp.today().normalize() - pd.Timedelta(days=92):
            warnings.append(
                "Fecha histórica fuera del dataset: no hay pronóstico para completar el clima del día; "
                "se usó el último clima conocido."
            )
            return warnings
        try:
            cell_row = self.cells[self.cells["cell_id"].astype(str) == cell]
            if cell_row.empty:
                return warnings
            payload = cell_row[["cell_id", "lat", "lon", "region_id"]].copy()
            payload["timezone"] = np.where(
                payload["region_id"] == "galapagos", "Pacific/Galapagos", "America/Guayaquil"
            )
            weather = OpenMeteoClient().daily_weather(
                payload,
                when.strftime("%Y-%m-%d"),
                when.strftime("%Y-%m-%d"),
                forecast=True,
                chunk_size=1,
            )
            if weather.empty:
                warnings.append("No se pudo obtener el pronóstico del día; se usó el último clima disponible.")
                return warnings
            weather_row = weather.iloc[0]
            for variable in WEATHER_VARIABLES:
                column = f"wx_{variable}_d0"
                if column in row and variable in weather_row:
                    value = weather_row[variable]
                    if pd.notna(value):
                        row[column] = value
        except Exception as exc:  # noqa: BLE001
            logger.warning("Pronóstico no disponible: %s", exc)
            warnings.append("Pronóstico meteorológico no disponible; se usó el último clima conocido.")
        return warnings

    def _top_factors(self, row: pd.Series, horizon: int, limit: int = 5) -> list[dict]:
        if self.importance.empty:
            return []
        subset = self.importance[self.importance["horizon"] == horizon].head(limit)
        factors = []
        for item in subset.itertuples(index=False):
            feature = str(item.feature)
            raw = row.get(feature)
            value = None
            if raw is not None and pd.notna(raw):
                try:
                    value = float(raw)
                except (TypeError, ValueError):
                    value = str(raw)
            factors.append(
                {
                    "feature": feature,
                    "value": value,
                    "importance": float(item.importance_mean),
                }
            )
        return factors

    # ---------------------------------------------------------------- predict
    def predict(
        self,
        latitude: float,
        longitude: float,
        when: str | date_type | pd.Timestamp,
        window_days: int = 7,
    ) -> dict:
        window_days = int(max(0, min(7, window_days)))
        if window_days not in self.bundle["horizons"]:
            available = sorted(self.bundle["horizons"])
            window_days = max([value for value in available if value <= window_days], default=available[0])
        when_ts = pd.Timestamp(when).normalize()
        cell, distance, warnings = self._resolve_cell(float(latitude), float(longitude))
        row, exact = self._load_row(cell, when_ts)
        if not exact:
            warnings.append(
                "La fecha consultada no está en el histórico exacto: se usó el último estado disponible "
                "hasta esa fecha y el calendario de la fecha solicitada."
            )
        self._update_calendar(row, when_ts)
        if not exact:
            warnings += self._update_forecast_weather(row, cell, when_ts, window_days)

        model = self.bundle["horizons"][window_days]
        features = self.bundle["feature_columns"][window_days]
        vector = np.array(
            [pd.to_numeric(row.get(column), errors="coerce") if row.get(column) is not None else np.nan for column in features],
            dtype=np.float32,
        ).reshape(1, -1)
        probability = float(model.predict_proba(vector)[0, 1])
        thresholds = self.bundle["thresholds"][window_days]
        level = str(risk_levels(np.array([probability]), thresholds)[0])
        completeness = float(np.mean(~np.isnan(vector))) if vector.size else 0.0

        static_row = self.cells[self.cells["cell_id"].astype(str) == cell]
        if not static_row.empty and int(static_row.iloc[0].get("is_galapagos", 0)) == 1:
            warnings.append(
                "Galápagos: la actividad volcánica puede generar detecciones térmicas que no son incendios."
            )

        return {
            "cell_id": cell,
            "latitude": float(latitude),
            "longitude": float(longitude),
            "cell_center": {
                "lat": float(static_row.iloc[0]["lat"]) if not static_row.empty else None,
                "lon": float(static_row.iloc[0]["lon"]) if not static_row.empty else None,
            },
            "distance_to_cell_km": round(distance, 2),
            "date": when_ts.strftime("%Y-%m-%d"),
            "window_days": window_days,
            "probability": round(probability, 6),
            "risk_level": level,
            "thresholds": thresholds,
            "model_version": self.bundle.get("version"),
            "calibration": self.bundle.get("calibration", {}).get(window_days),
            "data_completeness": round(completeness, 4),
            "top_factors": self._top_factors(row, window_days),
            "warnings": warnings,
            "disclaimer": (
                "Probabilidad basada en datos históricos NASA FIRMS, clima, DEM y NDVI. "
                "Una detección de foco de calor no equivale a un incendio confirmado."
            ),
        }

    def predict_grid(
        self,
        when: str | date_type | pd.Timestamp,
        window_days: int = 7,
    ) -> pd.DataFrame:
        """Predice todas las celdas de una vez para publicar una capa de mapa.

        Esta ruta de lote evita abrir el parquet una vez por celda. Está pensada
        para un job diario, no para solicitudes HTTP interactivas.
        """
        window_days = int(max(0, min(7, window_days)))
        available = sorted(self.bundle["horizons"])
        if window_days not in self.bundle["horizons"]:
            window_days = max([value for value in available if value <= window_days], default=available[0])
        when_ts = pd.Timestamp(when).normalize()
        dataset = pd.read_parquet(self.dataset_path)
        dataset["date"] = pd.to_datetime(dataset["date"]).dt.normalize()
        exact = dataset[dataset["date"] == when_ts].copy()
        if exact.empty:
            eligible = dataset[dataset["date"] <= when_ts].sort_values(["cell_id", "date"])
            exact = eligible.drop_duplicates("cell_id", keep="last").copy()
        if exact.empty:
            raise ValueError(f"La fecha {when_ts.date()} es anterior al historial disponible.")

        cells = self.cells.copy()
        cells["cell_id"] = cells["cell_id"].astype(str)
        exact["cell_id"] = exact["cell_id"].astype(str)
        frame = cells.merge(exact, on="cell_id", how="left", suffixes=("", "_history"))
        if frame.empty or frame["date"].isna().all():
            raise ValueError("No hay features históricas para las celdas del mapa.")

        self._update_calendar_frame(frame, when_ts)
        features = self.bundle["feature_columns"][window_days]
        matrix = np.column_stack(
            [pd.to_numeric(frame.get(column), errors="coerce").to_numpy(dtype=np.float32) for column in features]
        )
        probabilities = self.bundle["horizons"][window_days].predict_proba(matrix)[:, 1]
        thresholds = self.bundle["thresholds"][window_days]
        frame["probability"] = probabilities.astype(float)
        frame["risk_level"] = risk_levels(probabilities, thresholds).astype(str)
        frame["data_completeness"] = np.mean(~np.isnan(matrix), axis=1)
        frame["prediction_date"] = when_ts.strftime("%Y-%m-%d")
        frame["window_days"] = window_days
        frame["model_version"] = self.bundle.get("version")
        return frame[
            [
                "cell_id", "lat_idx", "lon_idx", "lat", "lon", "province", "province_id", "region", "region_id",
                "is_galapagos", "probability", "risk_level", "data_completeness", "prediction_date", "window_days", "model_version",
            ]
        ].copy()

    @staticmethod
    def _update_calendar_frame(frame: pd.DataFrame, when: pd.Timestamp) -> None:
        frame["month"] = when.month
        frame["day_of_year"] = int(when.day_of_year)
        frame["week_of_year"] = int(when.isocalendar().week)
        frame["weekday"] = when.day_of_week
        frame["is_weekend"] = int(when.day_of_week >= 5)
        frame["doy_sin"] = np.sin(2 * np.pi * int(when.day_of_year) / 365.25)
        frame["doy_cos"] = np.cos(2 * np.pi * int(when.day_of_year) / 365.25)


def predict_batch(
    predictor: FireRiskPredictor,
    input_csv: Path,
    output_csv: Path,
) -> pd.DataFrame:
    frame = pd.read_csv(input_csv)
    required = {"latitude", "longitude", "date"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Faltan columnas en {input_csv}: {sorted(missing)}")
    results = []
    for row in frame.itertuples(index=False):
        window = getattr(row, "window_days", 7)
        window = 7 if pd.isna(window) else int(window)
        results.append(
            predictor.predict(
                float(row.latitude),
                float(row.longitude),
                row.date,
                window_days=window,
            )
        )
    output = pd.DataFrame(results)
    output.to_csv(output_csv, index=False)
    return output


def load_metadata(path: Path | None = None) -> dict:
    settings = get_settings()
    meta_path = Path(path or settings.ml_dir / "fire_risk_dataset.meta.json")
    return json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
