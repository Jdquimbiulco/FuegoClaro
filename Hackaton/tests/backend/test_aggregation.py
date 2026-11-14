import pandas as pd

from app.domain.aggregation import build_summary, build_timeseries
from app.domain.models import FilterSpec


def sample_df():
    return pd.DataFrame(
        [
            {
                "id": "1",
                "sensor": "MODIS",
                "acq_date_local": "2024-01-01",
                "confidence_level": "nominal",
                "daynight": "D",
                "frp": 10.0,
                "region_id": "costa",
                "province_id": "ECU-G",
                "province": "Guayas",
            },
            {
                "id": "2",
                "sensor": "VIIRS",
                "acq_date_local": "2024-01-01",
                "confidence_level": "high",
                "daynight": "N",
                "frp": 5.0,
                "region_id": "costa",
                "province_id": "ECU-G",
                "province": "Guayas",
            },
            {
                "id": "3",
                "sensor": "VIIRS",
                "acq_date_local": "2024-01-02",
                "confidence_level": "low",
                "daynight": "D",
                "frp": None,
                "region_id": "sierra",
                "province_id": "ECU-P",
                "province": "Pichincha",
            },
        ]
    )


def test_build_summary_counts_and_shares():
    spec = FilterSpec(start_date="2024-01-01", end_date="2024-01-02")
    summary = build_summary(sample_df(), spec)
    assert summary["total"] == 3
    assert summary["active_days"] == 2
    assert summary["days_in_period"] == 2
    assert summary["by_sensor"][0]["sensor"] in {"MODIS", "VIIRS"}
    assert sum(item["count"] for item in summary["by_region"]) == 3
    assert summary["frp"]["valid"] == 2


def test_build_timeseries_month_granularity():
    spec = FilterSpec(start_date="2024-01-01", end_date="2024-01-31")
    ts = build_timeseries(sample_df(), spec, granularity="month")
    assert ts["granularity"] == "month"
    assert ts["series"]
    periods = {row["period"] for row in ts["series"]}
    assert periods == {"2024-01"}
    assert sum(row["count"] for row in ts["series"]) == 3
