"""Ingeniería de variables para el modelo de riesgo de incendios.

Todo el cálculo se hace sobre matrices densas ``celda x día`` para que los
lags, ventanas móviles y vecindarios sean rápidos incluso con ~3,5 M de filas.
Las funciones son puras y se reutilizan desde ``dataset.py`` y ``inference.py``.
"""

from __future__ import annotations

import json
import warnings
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", message="DataFrame is highly fragmented", category=pd.errors.PerformanceWarning)

from app.ml.grid import DEFAULT_GRID_STEP, haversine_km, neighbor_offsets

ALERT_CODES = {"quema_menor": 0, "alerta_media": 1, "alerta_roja": 2}
ALERT_LABELS = {value: key for key, value in ALERT_CODES.items()}

# Volcanes con actividad térmica en Galápagos. Se usan solo como variable
# estática de contexto, no para excluir detecciones.
GALAPAGOS_VOLCANOES = [
    ("Sierra Negra", -0.83, -91.17),
    ("Cerro Azul", -0.42, -91.12),
    ("Alcedo", -0.43, -91.12),
    ("Darwin", -0.18, -91.29),
    ("Wolf", 0.02, -91.35),
    ("Fernandina", -0.37, -91.57),
    ("Marchena", 0.33, -90.47),
    ("Pinta", 0.58, -90.75),
]


@dataclass
class DenseGrid:
    """Matriz celda x día y utilidades de ventanas/vecindarios."""

    cells: pd.DataFrame
    dates: pd.DatetimeIndex
    step: float = DEFAULT_GRID_STEP

    def __post_init__(self) -> None:
        self.cells = self.cells.reset_index(drop=True)
        self.dates = pd.DatetimeIndex(sorted(pd.to_datetime(self.dates).unique()))
        self.cell_ids = self.cells["cell_id"].astype(str).to_numpy()
        self.index = {value: position for position, value in enumerate(self.cell_ids)}
        self.start = self.dates[0]
        self.n_cells = len(self.cells)
        self.n_days = len(self.dates)
        self.row = (self.cells["lat_idx"].to_numpy() - int(self.cells["lat_idx"].min())).astype(int)
        self.col = (self.cells["lon_idx"].to_numpy() - int(self.cells["lon_idx"].min())).astype(int)
        self.raster_shape = (int(self.row.max()) + 1, int(self.col.max()) + 1)
        self.lat = self.cells["lat"].to_numpy(dtype=float)
        self.lon = self.cells["lon"].to_numpy(dtype=float)

    # --------------------------------------------------------------- matrices
    def day_positions(self, values) -> np.ndarray:
        return ((pd.to_datetime(values) - self.start).dt.days).to_numpy()

    def matrix_from_panel(self, panel: pd.DataFrame, column: str, fill: float = 0.0) -> np.ndarray:
        cell_position = panel["cell_id"].map(self.index).to_numpy()
        day_position = self.day_positions(panel["date"])
        matrix = np.full((self.n_cells, self.n_days), fill, dtype=np.float64)
        matrix[cell_position, day_position] = pd.to_numeric(panel[column], errors="coerce").fillna(fill).to_numpy()
        return matrix

    def assign(self, panel: pd.DataFrame, matrix: np.ndarray, name: str) -> None:
        cell_position = panel["cell_id"].map(self.index).to_numpy()
        day_position = self.day_positions(panel["date"])
        panel[name] = matrix[cell_position, day_position].astype(np.float32)

    # --------------------------------------------------------------- ventanas
    @staticmethod
    def shift(matrix: np.ndarray, periods: int = 1) -> np.ndarray:
        out = np.full_like(matrix, np.nan, dtype=np.float64)
        if periods <= 0:
            out[:] = matrix
        elif periods < matrix.shape[1]:
            out[:, periods:] = matrix[:, :-periods]
        return out

    @staticmethod
    def rolling_sum(matrix: np.ndarray, window: int, shift: int = 1) -> np.ndarray:
        shifted = DenseGrid.shift(matrix, shift)
        values = np.nan_to_num(shifted, nan=0.0)
        valid = (~np.isnan(shifted)).astype(np.float64)
        cumulative = np.concatenate([np.zeros((matrix.shape[0], 1)), np.cumsum(values, axis=1)], axis=1)
        counts = np.concatenate([np.zeros((matrix.shape[0], 1)), np.cumsum(valid, axis=1)], axis=1)
        index = np.arange(matrix.shape[1])
        low = np.maximum(0, index - window + 1)
        result = cumulative[:, index + 1] - cumulative[:, low]
        count = counts[:, index + 1] - counts[:, low]
        result[count == 0] = np.nan
        return result

    @classmethod
    def rolling_mean(cls, matrix: np.ndarray, window: int, shift: int = 1) -> np.ndarray:
        total = cls.rolling_sum(matrix, window, shift=shift)
        shifted = cls.shift(matrix, shift)
        valid = (~np.isnan(shifted)).astype(np.float64)
        cumulative = np.concatenate([np.zeros((matrix.shape[0], 1)), np.cumsum(valid, axis=1)], axis=1)
        index = np.arange(matrix.shape[1])
        low = np.maximum(0, index - window + 1)
        count = cumulative[:, index + 1] - cumulative[:, low]
        with np.errstate(invalid="ignore", divide="ignore"):
            return total / count

    @staticmethod
    def rolling_max(matrix: np.ndarray, window: int, shift: int = 1, chunk: int = 256) -> np.ndarray:
        shifted = DenseGrid.shift(matrix, shift)
        padded = np.pad(shifted, ((0, 0), (window - 1, 0)), constant_values=np.nan)
        out = np.full_like(matrix, np.nan, dtype=np.float64)
        for start in range(0, matrix.shape[0], chunk):
            stop = min(start + chunk, matrix.shape[0])
            block = padded[start:stop]
            windows = np.lib.stride_tricks.sliding_window_view(block, window, axis=1)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                out[start:stop] = np.nanmax(windows, axis=2)
        return out

    # ----------------------------------------------------------- vecindarios
    def neighbor_sum(self, matrix: np.ndarray, rings: int = 1, include_self: bool = True) -> np.ndarray:
        out = np.full_like(matrix, np.nan, dtype=np.float64)
        offsets = [(0, 0)] if include_self else []
        offsets += neighbor_offsets(rings)
        rows, cols = self.row, self.col
        for day in range(self.n_days):
            raster = np.zeros(self.raster_shape, dtype=np.float64)
            raster[rows, cols] = matrix[:, day]
            padded = np.pad(raster, rings, constant_values=np.nan)
            total = np.zeros_like(raster)
            for dlat, dlon in offsets:
                total += padded[rings + dlat : rings + dlat + raster.shape[0], rings + dlon : rings + dlon + raster.shape[1]]
            out[:, day] = total[rows, cols]
        return out

    def active_neighbors(self, matrix: np.ndarray, rings: int = 1) -> np.ndarray:
        binary = (matrix > 0).astype(np.float64)
        return self.neighbor_sum(binary, rings=rings, include_self=False)

    def distance_to_nearest(self, matrix: np.ndarray, rings: int = 3) -> np.ndarray:
        """Distancia (km) a la celda activa más cercana en los últimos ``rings`` anillos."""
        binary = (matrix > 0).astype(bool)
        out = np.full_like(matrix, np.nan, dtype=np.float64)
        rows, cols = self.row, self.col
        distances: dict[tuple[int, int], np.ndarray] = {}
        for dlat in range(-rings, rings + 1):
            for dlon in range(-rings, rings + 1):
                if dlat == 0 and dlon == 0:
                    continue
                distances[(dlat, dlon)] = haversine_km(
                    self.lat,
                    self.lon,
                    self.lat + dlat * self.step,
                    self.lon + dlon * self.step,
                )
        for day in range(self.n_days):
            active = np.zeros(self.raster_shape, dtype=bool)
            active[rows, cols] = binary[:, day]
            padded = np.pad(active, rings, constant_values=False)
            current = out[:, day]
            for (dlat, dlon), distance in distances.items():
                shifted = padded[
                    rings + dlat : rings + dlat + active.shape[0],
                    rings + dlon : rings + dlon + active.shape[1],
                ][rows, cols]
                update = shifted & np.isnan(current)
                current[update] = distance[update]
            out[:, day] = current
        return out


# --------------------------------------------------------------------------- agregados FIRMS
def detection_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega detecciones por celda/día (incluye columnas de evento vacías)."""
    if df.empty:
        return pd.DataFrame(
            columns=[
                "cell_id",
                "date",
                "det_count",
                "frp_sum",
                "frp_max",
                "night_count",
                "high_conf_count",
                "modis_count",
                "viirs_count",
                "mean_hour",
            ]
        )
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["acq_date_local"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["date"])
    frame["frp"] = pd.to_numeric(frame.get("frp"), errors="coerce").fillna(0.0)
    if "acq_time_local" in frame:
        # Acepta ``HH:MM``, ``HHMM`` y ``HHMMSS`` (el CSV canónico usa HH:MM).
        text = (
            frame["acq_time_local"]
            .astype(str)
            .str.strip()
            .str.replace(":", "", regex=False)
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(4)
        )
        hour = pd.to_numeric(text.str[:2], errors="coerce")
        minute = pd.to_numeric(text.str[2:4], errors="coerce")
        frame["mean_hour"] = hour + minute / 60.0
    else:
        frame["mean_hour"] = np.nan
    grouped = frame.groupby(["cell_id", "date"], observed=True)
    result = grouped.agg(
        det_count=("cell_id", "size"),
        frp_sum=("frp", "sum"),
        frp_max=("frp", "max"),
        night_count=("daynight", lambda values: int((values.astype(str).str.upper() == "N").sum())),
        high_conf_count=("confidence_level", lambda values: int((values.astype(str).str.lower() == "high").sum())),
        modis_count=("sensor", lambda values: int((values.astype(str).str.upper() == "MODIS").sum())),
        viirs_count=("sensor", lambda values: int((values.astype(str).str.upper() == "VIIRS").sum())),
        mean_hour=("mean_hour", "mean"),
    ).reset_index()
    return result


def event_tables(df: pd.DataFrame, events: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (histórico de eventos, agregado evento-celda-día)."""
    history_rows: list[dict] = []
    assignment_rows: list[dict] = []
    id_to_position = pd.Series(np.arange(len(df)), index=df["id"].astype(str))

    for event in events:
        event_id = str(event.get("id_evento", ""))
        level = str(event.get("nivel_alerta", "quema_menor"))
        history_rows.append(
            {
                "event_id": event_id,
                "rank": event.get("rank"),
                "nivel_alerta": level,
                "nivel_alerta_label": event.get("nivel_alerta_label"),
                "motivo_regla": event.get("motivo_regla"),
                "frp_total": event.get("frp_total"),
                "frp_max": event.get("frp_max"),
                "frp_medio": event.get("frp_medio"),
                "puntos_count": event.get("puntos_count"),
                "centro_lat": (event.get("centro") or [None, None])[0],
                "centro_lon": (event.get("centro") or [None, None])[1],
                "inicio": event.get("inicio"),
                "fin": event.get("fin"),
                "dias": json.dumps(event.get("dias", []), ensure_ascii=False),
                "diurnas": event.get("diurnas"),
                "nocturnas": event.get("nocturnas"),
                "sensores": json.dumps(event.get("sensores", []), ensure_ascii=False),
                "provincias": json.dumps(event.get("provincias", []), ensure_ascii=False),
                "geometria": json.dumps(event.get("geometria", {}), ensure_ascii=False),
            }
        )

        positions = id_to_position.reindex([str(value) for value in event.get("puntos_ids", [])]).dropna()
        if positions.empty:
            continue
        subset = df.iloc[positions.astype(int).to_numpy()]
        subset = subset.copy()
        subset["date"] = pd.to_datetime(subset["acq_date_local"], errors="coerce").dt.normalize()
        subset = subset.dropna(subset=["date"])
        for (cell, date), group in subset.groupby(["cell_id", "date"], observed=True):
            # Estadísticos del grupo celda-día, no del evento completo: el evento
            # puede extenderse en el futuro y no debe filtrar información.
            group_frp = (
                pd.to_numeric(group["frp"], errors="coerce").fillna(0.0)
                if "frp" in group
                else pd.Series(0.0, index=group.index)
            )
            group_night = (
                int((group["daynight"].astype(str).str.upper() == "N").sum())
                if "daynight" in group
                else 0
            )
            assignment_rows.append(
                {
                    "cell_id": str(cell),
                    "date": date,
                    "event_id": event_id,
                    "nivel_alerta": level,
                    "event_frp_total": float(group_frp.sum()),
                    "event_frp_max": float(group_frp.max()),
                    "event_puntos": int(len(group)),
                    "event_nocturnas": group_night,
                    "event_det_count": int(len(group)),
                }
            )

    history = pd.DataFrame(history_rows)
    assignments = pd.DataFrame(assignment_rows)
    if assignments.empty:
        return history, pd.DataFrame(
            columns=[
                "cell_id",
                "date",
                "event_count",
                "event_det_count",
                "event_frp_sum",
                "event_frp_max",
                "event_points_max",
                "event_alert_max",
                "event_night_count",
            ]
        )

    assignments["date"] = pd.to_datetime(assignments["date"]).dt.normalize()
    assignments["event_alert_code"] = assignments["nivel_alerta"].map(ALERT_CODES).fillna(0).astype(int)
    grouped = assignments.groupby(["cell_id", "date"], observed=True)
    daily = grouped.agg(
        event_count=("event_id", "nunique"),
        event_det_count=("event_det_count", "sum"),
        event_frp_sum=("event_frp_total", "sum"),
        event_frp_max=("event_frp_max", "max"),
        event_points_max=("event_puntos", "max"),
        event_alert_max=("event_alert_code", "max"),
        event_night_count=("event_nocturnas", "sum"),
    ).reset_index()
    return history, daily


# --------------------------------------------------------------------------- panel
def build_panel(cells: pd.DataFrame, dates: Iterable[pd.Timestamp]) -> pd.DataFrame:
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(list(dates)).unique()))
    n_cells, n_days = len(cells), len(dates)
    panel = pd.DataFrame(
        {
            "cell_id": np.repeat(cells["cell_id"].astype(str).to_numpy(), n_days),
            "date": np.tile(dates.to_numpy(), n_cells),
        }
    )
    panel = panel.merge(cells, on="cell_id", how="left", validate="many_to_one")
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    return panel


def merge_daily(panel: pd.DataFrame, daily: pd.DataFrame, fill_columns: list[str]) -> pd.DataFrame:
    if daily.empty:
        for column in fill_columns:
            panel[column] = 0.0
        return panel
    out = panel.merge(daily, on=["cell_id", "date"], how="left", validate="many_to_one")
    for column in fill_columns:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce").fillna(0.0)
    return out


def add_calendar(panel: pd.DataFrame) -> None:
    dates = pd.to_datetime(panel["date"])
    panel["year"] = dates.dt.year.astype("int16")
    panel["month"] = dates.dt.month.astype("int8")
    panel["day_of_year"] = dates.dt.day_of_year.astype("int16")
    panel["week_of_year"] = dates.dt.isocalendar().week.astype("int8")
    panel["weekday"] = dates.dt.day_of_week.astype("int8")
    panel["is_weekend"] = (panel["weekday"] >= 5).astype("int8")
    panel["doy_sin"] = np.sin(2 * np.pi * panel["day_of_year"] / 365.25)
    panel["doy_cos"] = np.cos(2 * np.pi * panel["day_of_year"] / 365.25)


def add_dense_features(panel: pd.DataFrame, grid: DenseGrid) -> None:
    """Lags, medias móviles y vecindarios de las variables FIRMS/eventos."""
    base_columns = [
        "det_count",
        "frp_sum",
        "frp_max",
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
    ]
    if "det_count" in panel and "mean_hour" in panel:
        panel.loc[panel["det_count"] <= 0, "mean_hour"] = np.nan
    for column in base_columns:
        if column not in panel:
            panel[column] = np.nan if column == "mean_hour" else 0.0
        fill_value = np.nan if column == "mean_hour" else 0.0
        panel[column] = pd.to_numeric(panel[column], errors="coerce").fillna(fill_value)

    matrices: dict[str, np.ndarray] = {}
    for column in base_columns:
        fill_value = np.nan if column == "mean_hour" else 0.0
        matrix = grid.matrix_from_panel(panel, column, fill=fill_value)
        matrices[column] = matrix

    for column in [
        "det_count",
        "event_det_count",
        "night_count",
        "high_conf_count",
        "modis_count",
        "viirs_count",
        "event_count",
    ]:
        matrix = matrices[column]
        for lag in (1, 2, 3, 7):
            grid.assign(panel, grid.shift(matrix, lag), f"{column}_lag{lag}")
        for window in (3, 7, 14, 30):
            grid.assign(panel, grid.rolling_sum(matrix, window), f"{column}_roll{window}")

    for column in ("frp_sum", "event_frp_sum"):
        matrix = matrices[column]
        grid.assign(panel, grid.shift(matrix, 1), f"{column}_lag1")
        for window in (7, 30):
            grid.assign(panel, grid.rolling_sum(matrix, window), f"{column}_roll{window}")

    for column in ("frp_max", "event_frp_max"):
        matrix = matrices[column]
        grid.assign(panel, grid.shift(matrix, 1), f"{column}_lag1")
        for window in (7, 30):
            grid.assign(panel, grid.rolling_max(matrix, window), f"{column}_roll{window}")

    for column in ("mean_hour", "event_points_max", "event_alert_max", "event_night_count"):
        matrix = matrices[column]
        grid.assign(panel, grid.shift(matrix, 1), f"{column}_lag1")
        grid.assign(panel, grid.rolling_mean(matrix, 7), f"{column}_roll7")

    # Ratios interpretables (evitan que el modelo dependa solo del total).
    with np.errstate(invalid="ignore", divide="ignore"):
        panel["viirs_share_lag1"] = panel["viirs_count_lag1"] / panel["det_count_lag1"].replace(0, np.nan)
        panel["night_share_lag1"] = panel["night_count_lag1"] / panel["det_count_lag1"].replace(0, np.nan)
        panel["event_share_lag1"] = panel["event_det_count_lag1"] / panel["det_count_lag1"].replace(0, np.nan)

    # Días desde el último incendio y nº de días con fuego en 30 días.
    fire = (matrices["event_det_count"] > 0).astype(float)
    days_since = np.full_like(fire, np.nan)
    last = np.full(grid.n_cells, -1, dtype=int)
    for day in range(grid.n_days):
        previous = last.copy()
        days_since[:, day] = np.where(previous >= 0, day - previous, np.nan)
        last = np.where(fire[:, day] > 0, day, last)
    grid.assign(panel, days_since, "days_since_fire")
    grid.assign(panel, grid.rolling_sum(fire, 30), "fire_days_roll30")

    # Vecindarios 3x3 y 5x5. Se desplazan un día para no usar información del
    # mismo día objetivo (crítico tanto en h=0 como en h>=1).
    for column, prefix in (("det_count", "det"), ("frp_sum", "frp"), ("event_det_count", "event")):
        matrix = grid.shift(matrices[column], 1)
        for rings, suffix in ((1, "3x3"), (2, "5x5")):
            grid.assign(panel, grid.neighbor_sum(matrix, rings=rings, include_self=True), f"{prefix}_sum_{suffix}_lag1")
        grid.assign(panel, grid.active_neighbors(matrix, rings=1), f"{prefix}_active_neighbors_3x3_lag1")

    fire_lag = grid.shift(fire, 1)
    grid.assign(panel, grid.neighbor_sum(fire_lag, rings=1, include_self=False), "fire_neighbors_3x3_lag1")
    grid.assign(panel, grid.distance_to_nearest(fire_lag, rings=3), "dist_nearest_fire_km")


def add_weather_features(panel: pd.DataFrame, grid: DenseGrid, weather: pd.DataFrame) -> pd.DataFrame:
    """Incorpora clima diario y sus lags/ventanas. ``weather`` viene de Open-Meteo."""
    if weather.empty:
        panel["weather_completeness"] = 0.0
        return panel
    weather = weather.copy()
    weather["date"] = pd.to_datetime(weather["date"]).dt.normalize()
    renamed = {column: f"wx_{column}" for column in weather.columns if column not in ("cell_id", "date")}
    weather = weather.rename(columns=renamed)
    values = [column for column in weather.columns if column.startswith("wx_")]
    panel = panel.merge(weather, on=["cell_id", "date"], how="left", validate="many_to_one")

    key_variables = [
        "wx_temperature_2m_mean",
        "wx_relative_humidity_2m_mean",
        "wx_wind_speed_10m_max",
        "wx_precipitation_sum",
        "wx_et0_fao_evapotranspiration",
        "wx_soil_moisture_0_to_7cm_mean",
        "wx_soil_moisture_7_to_28cm_mean",
    ]
    present = [column for column in key_variables if column in panel]
    panel["weather_completeness"] = (
        panel[present].notna().sum(axis=1) / len(key_variables) if present else 0.0
    )

    # D0 (solo se usa en el modelo h=0).
    for column in present:
        panel[f"{column}_d0"] = panel[column]

    # Lags y ventanas; el modelo h>=1 excluye las columnas ``_d0``.
    for column in present:
        matrix = grid.matrix_from_panel(panel, column, fill=np.nan)
        grid.assign(panel, grid.shift(matrix, 1), f"{column}_lag1")
        grid.assign(panel, grid.rolling_mean(matrix, 7), f"{column}_roll7")
        grid.assign(panel, grid.rolling_mean(matrix, 30), f"{column}_roll30")

    # Días secos consecutivos (precipitación < 1 mm) hasta D-1.
    if "wx_precipitation_sum" in panel:
        precip = grid.matrix_from_panel(panel, "wx_precipitation_sum", fill=np.nan)
        dry = np.where(np.isnan(precip), np.nan, (precip < 1.0).astype(float))
        dry_days = np.full_like(dry, np.nan)
        streak = np.zeros(grid.n_cells)
        for day in range(grid.n_days):
            dry_days[:, day] = streak
            streak = np.where(dry[:, day] == 1, streak + 1, 0)
        grid.assign(panel, dry_days, "dry_days")
    else:
        panel["dry_days"] = np.nan

    # Anomalías no disponibles por falta de variables.
    panel["tmax_anomaly_30"] = np.nan
    panel["drought_ratio_30"] = np.nan
    return panel


def add_ndvi_features(panel: pd.DataFrame, grid: DenseGrid, ndvi_daily: pd.DataFrame) -> pd.DataFrame:
    if ndvi_daily.empty:
        return panel.assign(
            ndvi_lag1=np.nan,
            ndvi_age_days=np.nan,
            ndvi_quality=np.nan,
            ndvi_available=np.int8(0),
        )
    ndvi = ndvi_daily.copy()
    ndvi["date"] = pd.to_datetime(ndvi["date"]).dt.normalize()
    ndvi = ndvi.rename(
        columns={"ndvi": "ndvi_value", "ndvi_quality": "ndvi_quality_value", "ndvi_age_days": "ndvi_age_value"}
    )
    panel = panel.merge(
        ndvi[["cell_id", "date", "ndvi_value", "ndvi_quality_value", "ndvi_age_value"]],
        on=["cell_id", "date"],
        how="left",
        validate="many_to_one",
    )
    matrix = grid.matrix_from_panel(panel, "ndvi_value", fill=np.nan)
    grid.assign(panel, grid.shift(matrix, 1), "ndvi_lag1")
    matrix_age = grid.matrix_from_panel(panel, "ndvi_age_value", fill=np.nan)
    grid.assign(panel, grid.shift(matrix_age, 1), "ndvi_age_days")
    matrix_quality = grid.matrix_from_panel(panel, "ndvi_quality_value", fill=np.nan)
    grid.assign(panel, grid.shift(matrix_quality, 1), "ndvi_quality")
    panel["ndvi_available"] = panel["ndvi_lag1"].notna().astype("int8")
    return panel


def add_static_features(
    panel: pd.DataFrame,
    grid: DenseGrid,
    terrain: pd.DataFrame | None,
    *,
    train_start: str,
    train_end: str,
) -> pd.DataFrame:
    cells = grid.cells
    if terrain is not None and not terrain.empty:
        panel = panel.merge(terrain, on="cell_id", how="left", validate="many_to_one")
    else:
        panel["elevation_m"] = np.nan
        panel["slope_deg"] = np.nan
        panel["aspect_sin"] = np.nan
        panel["aspect_cos"] = np.nan
        panel["terrain_roughness"] = np.nan

    # Frecuencia histórica calculada solo con el periodo de entrenamiento.
    train_mask = (pd.to_datetime(panel["date"]) >= pd.Timestamp(train_start)) & (
        pd.to_datetime(panel["date"]) <= pd.Timestamp(train_end)
    )
    fire = panel["event_det_count"] > 0
    cell_freq = fire[train_mask].groupby(panel.loc[train_mask, "cell_id"]).mean()
    panel["fire_freq_cell"] = panel["cell_id"].map(cell_freq).fillna(0.0)

    province_month = (
        panel.loc[train_mask, ["province_id", "month"]]
        .assign(fire=fire[train_mask].astype(int))
        .groupby(["province_id", "month"])["fire"]
        .mean()
        .rename("fire_freq_province_month")
    )
    province_index = pd.MultiIndex.from_frame(panel[["province_id", "month"]])
    panel["fire_freq_province_month"] = province_month.reindex(province_index).fillna(0.0).to_numpy()

    region_month = (
        panel.loc[train_mask, ["region_id", "month"]]
        .assign(fire=fire[train_mask].astype(int))
        .groupby(["region_id", "month"])["fire"]
        .mean()
        .rename("fire_freq_region_month")
    )
    region_index = pd.MultiIndex.from_frame(panel[["region_id", "month"]])
    panel["fire_freq_region_month"] = region_month.reindex(region_index).fillna(0.0).to_numpy()

    # Distancia a la celda con fuego histórico más cercana (solo train).
    active = cell_freq[cell_freq > 0].index
    if len(active):
        active_cells = cells[cells["cell_id"].isin(active)]
        distances = np.full(len(cells), np.inf)
        for row in active_cells.itertuples(index=False):
            distances = np.minimum(
                distances,
                haversine_km(cells["lat"], cells["lon"], float(row.lat), float(row.lon)),
            )
        panel["dist_hist_fire_km"] = panel["cell_id"].map(
            dict(zip(cells["cell_id"], distances))
        )
    else:
        panel["dist_hist_fire_km"] = np.nan

    # Distancia al volcán galapagueño más cercano (contexto, no exclusión).
    volcano_distance = np.full(len(cells), np.inf)
    for _, lat, lon in GALAPAGOS_VOLCANOES:
        volcano_distance = np.minimum(
            volcano_distance,
            haversine_km(cells["lat"], cells["lon"], lat, lon),
        )
    panel["dist_volcano_km"] = panel["cell_id"].map(dict(zip(cells["cell_id"], volcano_distance)))

    panel["province_code"] = panel["province_id"].astype("category").cat.codes.astype("int16")
    panel["region_code"] = panel["region_id"].astype("category").cat.codes.astype("int8")
    for region in ("costa", "sierra", "amazonia", "galapagos"):
        panel[f"region_{region}"] = (panel["region_id"] == region).astype("int8")
    if "is_galapagos" not in panel:
        panel["is_galapagos"] = 0
    panel["is_galapagos"] = panel["is_galapagos"].fillna(0).astype("int8")
    return panel


def add_labels(panel: pd.DataFrame, grid: DenseGrid, horizons: int = 7) -> None:
    fire = (panel["event_det_count"] > 0).astype("int8")
    matrix = grid.matrix_from_panel(panel, fire.name if hasattr(fire, "name") else "event_det_count")
    matrix = (matrix > 0).astype(float)
    per_day: dict[int, np.ndarray] = {}
    for horizon in range(horizons + 1):
        target = np.full((grid.n_cells, grid.n_days), np.nan)
        if horizon == 0:
            target[:] = matrix
        else:
            target[:, : grid.n_days - horizon] = matrix[:, horizon:]
        per_day[horizon] = target
        grid.assign(panel, target, f"y_d{horizon}")

    for horizon in range(horizons + 1):
        window = np.full((grid.n_cells, grid.n_days), np.nan)
        stack = np.stack([per_day[h] for h in range(horizon + 1)], axis=0)
        valid = ~np.isnan(stack).any(axis=0)
        window[valid] = np.nanmax(stack[:, valid], axis=0)
        grid.assign(panel, window, f"y_within_{horizon}")


def label_columns(horizons: int = 7) -> list[str]:
    columns = [f"y_d{h}" for h in range(horizons + 1)]
    columns += [f"y_within_{h}" for h in range(horizons + 1)]
    return columns
