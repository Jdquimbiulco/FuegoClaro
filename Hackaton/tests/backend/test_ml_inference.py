from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.external import OpenMeteoClient, _parse_ndvi_csv, ndvi_to_daily
from app.ml.inference import FireRiskPredictor
from app.ml.training import feature_columns, train


def _synthetic_dataset() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", "2026-11-12", freq="D")
    cells = ["0_0", "1_1"]
    rows = []
    rng = np.random.default_rng(7)
    for cell in cells:
        for when in dates:
            x1 = float(rng.random())
            x2 = float(rng.normal())
            fire = int(x1 > 0.85)
            rows.append(
                {
                    "cell_id": cell,
                    "date": when,
                    "lat": 0.05 if cell == "0_0" else 1.15,
                    "lon": 0.05 if cell == "0_0" else 1.15,
                    "province": "Pichincha",
                    "timezone": "America/Guayaquil",
                    "is_galapagos": 0,
                    "month": when.month,
                    "day_of_year": when.day_of_year,
                    "x1": x1,
                    "x2": x2,
                    "fire_freq_cell": 0.1 if cell == "0_0" else 0.2,
                    "y_within_0": fire,
                    "y_within_7": fire,
                }
            )
    return pd.DataFrame(rows)


def test_train_and_predict_roundtrip(tmp_path):
    dataset = _synthetic_dataset()
    dataset_path = tmp_path / "fire_risk_dataset.parquet"
    dataset.to_parquet(dataset_path, index=False)
    static = pd.DataFrame(
        [
            {
                "cell_id": "0_0",
                "lat": 0.05,
                "lon": 0.05,
                "lat_idx": 0,
                "lon_idx": 0,
                "province": "Pichincha",
                "province_id": "pichincha",
                "region": "Sierra",
                "region_id": "sierra",
                "is_galapagos": 0,
            },
            {
                "cell_id": "1_1",
                "lat": 1.15,
                "lon": 1.15,
                "lat_idx": 1,
                "lon_idx": 1,
                "province": "Pichincha",
                "province_id": "pichincha",
                "region": "Sierra",
                "region_id": "sierra",
                "is_galapagos": 0,
            },
        ]
    )
    static_path = tmp_path / "cells_static.parquet"
    static.to_parquet(static_path, index=False)

    result = train(
        dataset_path,
        tmp_path,
        horizons=[0],
        negative_ratio=5,
        importance=False,
    )
    assert 0 in result["horizons"]
    assert result["thresholds"][0]["q50"] is not None

    predictor = FireRiskPredictor(
        model_path=tmp_path / "risk_model.joblib",
        dataset_path=dataset_path,
        static_path=static_path,
        importance_path=tmp_path / "missing.csv",
    )
    prediction = predictor.predict(0.05, 0.05, "2025-06-01", window_days=0)
    assert 0.0 <= prediction["probability"] <= 1.0
    assert prediction["risk_level"] in {"Bajo", "Medio", "Alto", "Extremo"}
    assert prediction["cell_id"] == "0_0"
    assert prediction["date"] == "2025-06-01"
    assert prediction["data_completeness"] > 0.5


def test_feature_columns_do_not_include_same_day_raw_sources():
    dataset = pd.DataFrame(
        {
            "x": [1.0, 2.0],
            "wx_temperature_2m_max": [20.0, 21.0],
            "wx_temperature_2m_max_d0": [20.0, 21.0],
            "wx_temperature_2m_max_lag1": [19.0, 20.0],
            "wx_temperature_2m_max_roll7": [18.0, 19.0],
            "ndvi_value": [0.5, 0.6],
            "ndvi_lag1": [0.4, 0.5],
            "frp_mean": [1.0, 2.0],
            "weather_completeness": [1.0, 1.0],
            "y_within_0": [0, 0],
        }
    )
    h0 = feature_columns(dataset, 0)
    h1 = feature_columns(dataset, 1)
    assert "x" in h0
    assert "wx_temperature_2m_max_d0" in h0
    assert "wx_temperature_2m_max" not in h0
    assert "wx_temperature_2m_max_lag1" in h0
    assert "wx_temperature_2m_max_roll7" in h0
    assert "ndvi_value" not in h0
    assert "ndvi_lag1" in h0
    assert "frp_mean" not in h0
    assert "weather_completeness" in h0
    assert "wx_temperature_2m_max_d0" not in h1
    assert "weather_completeness" not in h1
    assert "wx_temperature_2m_max_lag1" in h1


def test_ndvi_parser_and_daily_fill():
    frame = pd.DataFrame(
        {
            "ID": ["0_0", "0_0", "0_0"],
            "Date": ["2025-01-01", "2025-01-17", "2025-02-02"],
            "MOD13Q1_061_250m_16_days_NDVI": [5000, -3000, 6000],
            "MOD13Q1_061_250m_16_days_pixel_reliability": [0, 0, 3],
        }
    )
    parsed = _parse_ndvi_csv(frame)
    assert len(parsed) == 3
    assert parsed["ndvi"].iloc[0] == 0.5
    assert np.isnan(parsed["ndvi"].iloc[1])
    assert np.isnan(parsed["ndvi"].iloc[2])  # calidad 3 = nublado

    cells = pd.DataFrame({"cell_id": ["0_0"], "lat": [0.05], "lon": [0.05]})
    dates = pd.date_range("2025-01-01", "2025-02-05", freq="D")
    daily = ndvi_to_daily(parsed, cells, dates)
    assert len(daily) == len(dates)
    assert daily["ndvi"].notna().any()
    assert daily["ndvi_age_days"].max() <= 16
