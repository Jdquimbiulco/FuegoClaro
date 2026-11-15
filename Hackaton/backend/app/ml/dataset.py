"""Construcción del dataset supervisado de riesgo de incendios.

Uso típico (desde ``Hackaton/``):

    python scripts/build_fire_risk_dataset.py --grid 0.1 --start 2022-01-01 --end 2026-11-12

El resultado principal es ``data/processed/ml/fire_risk_dataset.parquet`` con
una fila por celda y día, variables FIRMS/eventos, clima, DEM, NDVI y los
targets multihorizonte ``y_d0..y_d7`` / ``y_within_0..y_within_7``.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from app.core.config import get_settings
from app.domain.fire_events import detect_fire_events
from app.ml.external import AppEEARSClient, DemProvider, OpenMeteoClient, ndvi_to_daily
from app.ml.features import (
    DenseGrid,
    add_calendar,
    add_dense_features,
    add_labels,
    add_ndvi_features,
    add_static_features,
    add_weather_features,
    build_panel,
    detection_daily,
    event_tables,
    label_columns,
    merge_daily,
)
from app.ml.grid import DEFAULT_GRID_STEP, assign_cell_ids, land_cells

logger = logging.getLogger(__name__)

RAW_WEATHER_COLUMNS = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_min",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "precipitation_sum",
    "vapor_pressure_deficit_max",
    "et0_fao_evapotranspiration",
    "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
    "shortwave_radiation_sum",
]

BASE_AGGREGATE_COLUMNS = [
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

KEY_COLUMNS = [
    "cell_id",
    "date",
    "lat_idx",
    "lon_idx",
    "lat",
    "lon",
    "province",
    "province_id",
    "region",
    "region_id",
    "is_galapagos",
    "year",
    "month",
    "day_of_year",
    "week_of_year",
    "weekday",
    "is_weekend",
    "doy_sin",
    "doy_cos",
]


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


def _load_detections(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"No existe el dataset de detecciones: {path}")
    frame = pd.read_csv(path, low_memory=False)
    required = {"id", "latitude", "longitude", "acq_date_local"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en {path}: {sorted(missing)}")
    for column in ("latitude", "longitude", "frp"):
        if column in frame:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["latitude", "longitude", "acq_date_local"]).reset_index(drop=True)
    frame["acq_date_local"] = pd.to_datetime(frame["acq_date_local"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["acq_date_local"]).reset_index(drop=True)
    return frame


def _feature_groups(columns: list[str]) -> dict[str, list[str]]:
    groups: dict[str, list[str]] = {
        "keys": [],
        "calendar": [],
        "firms_events": [],
        "spatial": [],
        "weather": [],
        "terrain": [],
        "ndvi": [],
        "static": [],
        "labels": [],
    }
    for column in columns:
        if column in KEY_COLUMNS or column in {"fire_day"}:
            groups["keys"].append(column)
        elif column.startswith("y_") or column.startswith("y_d"):
            groups["labels"].append(column)
        elif column.startswith("wx_") or column in {"dry_days", "tmax_anomaly_30", "drought_ratio_30", "weather_completeness"}:
            groups["weather"].append(column)
        elif column in {"elevation_m", "slope_deg", "aspect_sin", "aspect_cos", "terrain_roughness"}:
            groups["terrain"].append(column)
        elif column.startswith("ndvi"):
            groups["ndvi"].append(column)
        elif column.startswith("region_") or column in {
            "fire_freq_cell",
            "fire_freq_province_month",
            "fire_freq_region_month",
            "dist_hist_fire_km",
            "dist_volcano_km",
            "province_code",
            "region_code",
        }:
            groups["static"].append(column)
        elif any(token in column for token in ("3x3", "5x5", "nearest_fire", "active_neighbors", "share_lag")):
            groups["spatial"].append(column)
        elif column in {"year", "month", "day_of_year", "week_of_year", "weekday", "is_weekend", "doy_sin", "doy_cos"}:
            groups["calendar"].append(column)
        elif column.startswith(("det_", "frp_", "night_", "high_conf_", "modis_", "viirs_", "event_", "mean_hour", "days_since_fire", "fire_days")):
            groups["firms_events"].append(column)
    return groups


def _leakage_checks(dataset: pd.DataFrame, cells: int, dates: int) -> dict:
    duplicates = int(dataset.duplicated(["cell_id", "date"]).sum())
    checks = {
        "unique_cell_date": duplicates == 0,
        "complete_panel": len(dataset) == cells * dates,
        "duplicates": duplicates,
        "dates": int(dataset["date"].nunique()),
    }
    sample = dataset.sample(min(5000, len(dataset)), random_state=42) if len(dataset) else dataset
    for horizon in range(8):
        label = f"y_within_{horizon}"
        per_day = [f"y_d{index}" for index in range(horizon + 1)]
        if label not in sample or not all(column in sample for column in per_day):
            checks[label] = None
            continue
        values = sample[per_day].to_numpy(dtype=float)
        valid = ~np.isnan(values).any(axis=1)
        expected = np.nanmax(values[valid], axis=1) if valid.any() else []
        checks[label] = bool(np.allclose(sample.loc[valid, label].to_numpy(dtype=float), expected))
    return checks


def build_dataset(
    *,
    grid_step: float = DEFAULT_GRID_STEP,
    start: str = "2022-01-01",
    end: str = "2026-11-12",
    detections_path: Path | None = None,
    output_dir: Path | None = None,
    skip_weather: bool = False,
    skip_dem: bool = False,
    skip_ndvi: bool = False,
    refresh_weather: bool = False,
    refresh_ndvi: bool = False,
    refresh_events: bool = False,
    include_galapagos: bool = True,
    limit_cells: int | None = None,
    weather_chunk: int = 25,
    ndvi_chunk: int = 500,
    ndvi_timeout: int = 7200,
) -> dict:
    """Construye y persiste el dataset. Devuelve el manifiesto generado."""
    _configure_logging()
    settings = get_settings()
    output_dir = Path(output_dir or settings.ml_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detections_path = Path(detections_path or settings.detections_file)

    start_date = pd.Timestamp(start).normalize()
    end_date = pd.Timestamp(end).normalize()
    dates = pd.date_range(start_date, end_date, freq="D")

    logger.info("Cargando detecciones desde %s", detections_path)
    detections = _load_detections(detections_path)
    detections = assign_cell_ids(detections, step=grid_step)
    logger.info("Detecciones válidas: %s", len(detections))

    cache_key = hashlib.sha1(
        json.dumps(
            {
                "path": str(detections_path),
                "mtime": detections_path.stat().st_mtime,
                "size": detections_path.stat().st_size,
                "grid_step": grid_step,
            },
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:16]
    event_cache = settings.cache_dir / "events" / f"{cache_key}.joblib"
    if event_cache.exists() and not refresh_events:
        logger.info("Reutilizando eventos cacheados (%s)", event_cache.name)
        events, event_history, event_daily = joblib.load(event_cache)
    else:
        logger.info("Construyendo eventos con ST-DBSCAN...")
        events = detect_fire_events(detections)
        event_history, event_daily = event_tables(detections, events)
        event_cache.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump((events, event_history, event_daily), event_cache)
    logger.info("Eventos detectados: %s", len(events))

    detection_agg = detection_daily(detections)

    logger.info("Construyendo cuadrícula terrestre (paso %.3f°)...", grid_step)
    cells = land_cells(step=grid_step).copy()
    if not include_galapagos:
        cells = cells[cells["region_id"] != "galapagos"].reset_index(drop=True)
    if limit_cells and limit_cells < len(cells):
        cells = cells.sample(n=limit_cells, random_state=42).sort_values(["lat_idx", "lon_idx"]).reset_index(drop=True)
        logger.warning("Modo de prueba: solo %s celdas", len(cells))
    cells["timezone"] = np.where(cells["region_id"] == "galapagos", "Pacific/Galapagos", "America/Guayaquil")
    logger.info("Celdas: %s | días: %s", len(cells), len(dates))

    panel = build_panel(cells, dates)
    panel = merge_daily(panel, detection_agg, BASE_AGGREGATE_COLUMNS[:8])
    panel = merge_daily(panel, event_daily, BASE_AGGREGATE_COLUMNS[8:])
    panel["frp_mean"] = np.where(panel["det_count"] > 0, panel["frp_sum"] / panel["det_count"], 0.0)
    add_calendar(panel)

    grid = DenseGrid(cells, dates, step=grid_step)
    logger.info("Calculando lags, ventanas y vecindarios FIRMS...")
    add_dense_features(panel, grid)
    panel = panel.copy()

    weather = pd.DataFrame()
    terrain = pd.DataFrame()
    ndvi = pd.DataFrame()

    if skip_weather:
        logger.warning("Clima omitido (--skip-weather)")
        panel = add_weather_features(panel, grid, pd.DataFrame())
    else:
        logger.info("Descargando clima diario de Open-Meteo...")
        client = OpenMeteoClient(cache_dir=settings.cache_dir)
        weather = client.daily_weather(
            cells[["cell_id", "lat", "lon", "region_id", "timezone"]],
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            refresh=refresh_weather,
            chunk_size=weather_chunk,
        )
        logger.info("Filas de clima: %s", len(weather))
        weather.to_parquet(output_dir / "weather_daily.parquet", index=False)
        panel = add_weather_features(panel, grid, weather)

    if skip_dem:
        logger.warning("DEM omitido (--skip-dem)")
    else:
        logger.info("Descargando DEM y calculando pendiente/aspecto...")
        try:
            terrain = DemProvider(client=OpenMeteoClient(cache_dir=settings.cache_dir)).terrain(
                cells, refresh=refresh_weather, step=grid_step
            )
            terrain.to_parquet(output_dir / "cells_terrain.parquet", index=False)
        except Exception as exc:  # noqa: BLE001
            logger.warning("No se pudo obtener DEM: %s", exc)
            terrain = pd.DataFrame()

    if skip_ndvi:
        logger.warning("NDVI omitido (--skip-ndvi)")
        panel = add_ndvi_features(panel, grid, pd.DataFrame())
    else:
        logger.info("Solicitando NDVI a NASA AppEEARS...")
        try:
            ndvi_client = AppEEARSClient(cache_dir=settings.cache_dir, timeout_seconds=ndvi_timeout)
            ndvi = ndvi_client.fetch_ndvi(
                cells[["cell_id", "lat", "lon"]],
                start_date.strftime("%Y-%m-%d"),
                end_date.strftime("%Y-%m-%d"),
                refresh=refresh_ndvi,
                chunk_size=ndvi_chunk,
            )
            if not ndvi.empty:
                ndvi_daily = ndvi_to_daily(ndvi, cells, dates)
                ndvi_daily.to_parquet(output_dir / "ndvi_daily.parquet", index=False)
                panel = add_ndvi_features(panel, grid, ndvi_daily)
            else:
                logger.warning("NDVI vacío; se continúa sin vegetación")
                panel = add_ndvi_features(panel, grid, pd.DataFrame())
        except Exception as exc:  # noqa: BLE001
            logger.warning("NDVI falló: %s", exc)
            panel = add_ndvi_features(panel, grid, pd.DataFrame())

    frequency_start = max(start_date, pd.Timestamp("2022-01-01"))
    frequency_end = min(end_date, pd.Timestamp("2024-12-31"))
    panel = add_static_features(
        panel,
        grid,
        terrain,
        train_start=frequency_start.strftime("%Y-%m-%d"),
        train_end=frequency_end.strftime("%Y-%m-%d"),
    )
    panel = panel.copy()
    panel["fire_day"] = (panel["event_det_count"] > 0).astype("int8")
    add_labels(panel, grid, horizons=7)

    # Guardar estado compacto y estáticos reutilizables por la inferencia.
    static_columns = [
        "lat",
        "lon",
        "lat_idx",
        "lon_idx",
        "province",
        "province_id",
        "region",
        "region_id",
        "is_galapagos",
        "elevation_m",
        "slope_deg",
        "terrain_roughness",
        "fire_freq_cell",
        "dist_hist_fire_km",
        "dist_volcano_km",
        "province_code",
        "region_code",
        "region_costa",
        "region_sierra",
        "region_amazonia",
        "region_galapagos",
    ]
    static_columns = [column for column in static_columns if column in panel]
    cells_static = panel.groupby("cell_id", observed=True)[static_columns].first().reset_index()
    cells_static.to_parquet(output_dir / "cells_static.parquet", index=False)

    aggregate_columns = ["cell_id", "date", *[c for c in BASE_AGGREGATE_COLUMNS if c in panel], "fire_day"]
    aggregate_columns += [column for column in panel.columns if column.startswith("wx_") and not column.endswith(("_lag1", "_roll7", "_roll30", "_d0"))]
    aggregate_columns = list(dict.fromkeys(aggregate_columns))
    panel[aggregate_columns].to_parquet(output_dir / "cell_day_aggregates.parquet", index=False)

    # Downcast de variables continuas para reducir el tamaño del Parquet.
    for column in panel.select_dtypes(include=["float64"]).columns:
        panel[column] = panel[column].astype(np.float32)

    dataset_path = output_dir / "fire_risk_dataset.parquet"
    logger.info("Guardando dataset (%s filas, %s columnas)...", len(panel), len(panel.columns))
    panel.to_parquet(dataset_path, index=False, compression="zstd")

    if event_history.empty:
        event_history = pd.DataFrame(
            columns=[
                "event_id",
                "rank",
                "nivel_alerta",
                "nivel_alerta_label",
                "motivo_regla",
                "frp_total",
                "frp_max",
                "frp_medio",
                "puntos_count",
                "centro_lat",
                "centro_lon",
                "inicio",
                "fin",
                "dias",
                "diurnas",
                "nocturnas",
                "sensores",
                "provincias",
                "geometria",
            ]
        )
    event_history.to_parquet(output_dir / "fire_events_history.parquet", index=False)

    labels = label_columns(7)
    positive_counts = {
        column: int(pd.to_numeric(panel[column], errors="coerce").fillna(0).sum())
        for column in labels
        if column in panel
    }
    base_rates = {
        column: float(pd.to_numeric(panel[column], errors="coerce").mean())
        for column in labels
        if column in panel
    }
    feature_groups = _feature_groups(list(panel.columns))
    missingness = (
        panel[feature_groups["weather"] + feature_groups["ndvi"] + feature_groups["terrain"]]
        .isna()
        .mean()
        .sort_values(ascending=False)
        .head(30)
        .round(4)
        .to_dict()
        if len(panel)
        else {}
    )
    checks = _leakage_checks(panel, len(cells), len(dates))

    warnings: list[str] = []
    if skip_weather:
        warnings.append("Clima omitido por --skip-weather.")
    if skip_dem:
        warnings.append("DEM omitido por --skip-dem.")
    if skip_ndvi or ndvi.empty:
        warnings.append("NDVI no disponible; el modelo usará solo clima y FIRMS.")
    if not include_galapagos:
        warnings.append("Galápagos excluido del dataset.")
    warnings.append("Detección satelital ≠ incendio confirmado; ausencia de detección ≠ ausencia de fuego.")

    manifest = {
        "dataset_version": f"fuegoclaro-risk-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "grid_step_degrees": grid_step,
        "date_range": {"start": start_date.strftime("%Y-%m-%d"), "end": end_date.strftime("%Y-%m-%d")},
        "cells": int(len(cells)),
        "rows": int(len(panel)),
        "columns": int(len(panel.columns)),
        "detections": int(len(detections)),
        "events": int(len(events)),
        "positive_counts": positive_counts,
        "base_rates": base_rates,
        "feature_groups": feature_groups,
        "missingness": {key: float(value) for key, value in missingness.items()},
        "leakage_checks": checks,
        "sources": {
            "firms": str(detections_path),
            "weather": "Open-Meteo Archive (ERA5) / Forecast" if not skip_weather else None,
            "dem": "Open-Meteo Elevation (Copernicus GLO-90)" if not skip_dem else None,
            "ndvi": "NASA AppEEARS MOD13Q1.061 250m 16-day NDVI" if not ndvi.empty else None,
        },
        "parameters": {
            "include_galapagos": include_galapagos,
            "limit_cells": limit_cells,
            "skip_weather": skip_weather,
            "skip_dem": skip_dem,
            "skip_ndvi": skip_ndvi,
        },
        "warnings": warnings,
        "files": {
            "dataset": str(dataset_path.name),
            "events": "fire_events_history.parquet",
            "static": "cells_static.parquet",
            "aggregates": "cell_day_aggregates.parquet",
        },
    }
    (output_dir / "fire_risk_dataset.meta.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("Listo: %s", dataset_path)
    logger.info("Positivos y_within_7: %s", positive_counts.get("y_within_7"))
    return manifest
