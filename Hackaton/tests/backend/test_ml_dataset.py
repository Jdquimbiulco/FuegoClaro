from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.features import (
    DenseGrid,
    add_calendar,
    add_dense_features,
    add_labels,
    add_ndvi_features,
    add_weather_features,
    build_panel,
    detection_daily,
    event_tables,
)
from app.ml.grid import assign_cell_ids, cell_centers, cell_id, land_cells


def _cells() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cell_id": cell_id(0, 0),
                "lat_idx": 0,
                "lon_idx": 0,
                "lat": 0.05,
                "lon": 0.05,
                "province": "Pichincha",
                "province_id": "pichincha",
                "region": "Sierra",
                "region_id": "sierra",
                "is_galapagos": 0,
            },
            {
                "cell_id": cell_id(0, 1),
                "lat_idx": 0,
                "lon_idx": 1,
                "lat": 0.05,
                "lon": 0.15,
                "province": "Pichincha",
                "province_id": "pichincha",
                "region": "Sierra",
                "region_id": "sierra",
                "is_galapagos": 0,
            },
        ]
    )


def _detections() -> pd.DataFrame:
    rows = [
        {
            "id": "a1",
            "latitude": 0.05,
            "longitude": 0.05,
            "acq_date_local": "2025-01-02",
            "acq_time_local": "1400",
            "daynight": "D",
            "frp": 10.0,
            "sensor": "VIIRS",
            "confidence_level": "high",
        },
        {
            "id": "a2",
            "latitude": 0.051,
            "longitude": 0.051,
            "acq_date_local": "2025-01-02",
            "acq_time_local": "1430",
            "daynight": "N",
            "frp": 20.0,
            "sensor": "MODIS",
            "confidence_level": "nominal",
        },
        {
            "id": "b1",
            "latitude": 0.05,
            "longitude": 0.15,
            "acq_date_local": "2025-01-04",
            "acq_time_local": "1500",
            "daynight": "D",
            "frp": 5.0,
            "sensor": "VIIRS",
            "confidence_level": "high",
        },
    ]
    frame = pd.DataFrame(rows)
    frame["acq_date_local"] = pd.to_datetime(frame["acq_date_local"])
    return assign_cell_ids(frame)


def test_grid_cell_ids_and_centers():
    lat, lon = cell_centers(np.array([0, 1]), np.array([0, 1]), step=0.1)
    assert np.allclose(lat, [0.05, 0.15])
    assert np.allclose(lon, [0.05, 0.15])
    assert cell_id(0, 0) == "0_0"
    assert cell_id(-1, 2) == "-1_2"


def test_land_cells_are_inside_ecuador():
    cells = land_cells(step=0.1)
    assert len(cells) > 1000
    assert cells["cell_id"].is_unique
    assert (cells["is_galapagos"] == 1).any()
    assert cells["region_id"].notna().all()


def test_detection_aggregation_and_events():
    detections = _detections()
    agg = detection_daily(detections)
    assert len(agg) == 2
    first = agg[agg["cell_id"] == cell_id(0, 0)].iloc[0]
    assert first["det_count"] == 2
    assert first["frp_sum"] == 30.0
    assert first["night_count"] == 1
    assert first["modis_count"] == 1
    assert first["viirs_count"] == 1
    assert abs(first["mean_hour"] - 14.25) < 1e-6

    from app.domain.fire_events import detect_fire_events

    events = detect_fire_events(detections)
    history, daily = event_tables(detections, events)
    assert not history.empty
    assert not daily.empty
    assert daily["event_det_count"].sum() == 3


def test_panel_features_are_lagged_and_labels_are_future():
    cells = _cells()
    dates = pd.date_range("2025-01-01", periods=6, freq="D")
    panel = build_panel(cells, dates)
    detections = _detections()
    panel = panel.merge(detection_daily(detections), on=["cell_id", "date"], how="left")
    for column in ("det_count", "frp_sum", "frp_max", "night_count", "high_conf_count", "modis_count", "viirs_count"):
        panel[column] = panel[column].fillna(0.0)
    panel["mean_hour"] = panel.get("mean_hour", np.nan)
    panel["event_count"] = 0.0
    panel["event_det_count"] = 0.0
    panel["event_frp_sum"] = 0.0
    panel["event_frp_max"] = 0.0
    panel["event_points_max"] = 0.0
    panel["event_alert_max"] = 0.0
    panel["event_night_count"] = 0.0
    # Fuego en la celda 0_0 el 2 de enero y en 0_1 el 4 de enero.
    panel.loc[(panel["cell_id"] == cell_id(0, 0)) & (panel["date"] == "2025-01-02"), "event_det_count"] = 2
    panel.loc[(panel["cell_id"] == cell_id(0, 1)) & (panel["date"] == "2025-01-04"), "event_det_count"] = 1
    add_calendar(panel)
    grid = DenseGrid(cells, dates, step=0.1)
    add_dense_features(panel, grid)
    panel = add_weather_features(
        panel,
        grid,
        pd.DataFrame(
            {
                "cell_id": np.repeat(cells["cell_id"], len(dates)),
                "date": np.tile(dates, len(cells)),
                "temperature_2m_max": np.arange(len(panel), dtype=float),
                "precipitation_sum": 0.0,
            }
        ),
    )
    panel = add_ndvi_features(panel, grid, pd.DataFrame())
    add_labels(panel, grid, horizons=2)

    target = panel[(panel["cell_id"] == cell_id(0, 0)) & (panel["date"] == "2025-01-03")].iloc[0]
    assert target["y_d0"] == 0.0
    assert target["y_within_1"] == 0.0
    previous = panel[(panel["cell_id"] == cell_id(0, 0)) & (panel["date"] == "2025-01-02")].iloc[0]
    assert previous["y_d0"] == 1.0
    assert previous["y_within_1"] == 1.0
    after = panel[(panel["cell_id"] == cell_id(0, 0)) & (panel["date"] == "2025-01-01")].iloc[0]
    assert after["y_within_1"] == 1.0
    assert pd.isna(after["det_count_lag1"])
    assert after["y_within_2"] == 1.0

    # No leakage: el lag 1 del 2 de enero usa el 1 de enero, no el propio día.
    day2 = panel[(panel["cell_id"] == cell_id(0, 0)) & (panel["date"] == "2025-01-02")].iloc[0]
    day1 = panel[(panel["cell_id"] == cell_id(0, 0)) & (panel["date"] == "2025-01-01")].iloc[0]
    assert day2["det_count_lag1"] == day1["det_count"]
    assert day2["det_count_lag1"] != day2["det_count"]
