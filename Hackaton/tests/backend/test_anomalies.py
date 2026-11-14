import pandas as pd

from app.domain.anomalies import detect_anomalies
from app.domain.models import FilterSpec


def test_detect_anomalies_flags_high_count_day():
    rows = []
    # Baseline: 2022 and 2023, Jan 10 +/- window has 1 detection per day per sensor
    for year in (2022, 2023):
        for day in range(1, 21):
            rows.append(
                {
                    "id": f"b-{year}-{day}",
                    "sensor": "MODIS",
                    "region_id": "costa",
                    "province_id": "ECU-G",
                    "acq_date_local": f"{year}-01-{day:02d}",
                }
            )
    # Evaluated year 2024: very high on Jan 10
    for i in range(20):
        rows.append(
            {
                "id": f"h-2024-{i}",
                "sensor": "MODIS",
                "region_id": "costa",
                "province_id": "ECU-G",
                "acq_date_local": "2024-01-10",
            }
        )
    # some normal days in 2024 to be realistic
    for day in range(1, 21):
        if day == 10:
            continue
        rows.append(
            {
                "id": f"n-2024-{day}",
                "sensor": "MODIS",
                "region_id": "costa",
                "province_id": "ECU-G",
                "acq_date_local": f"2024-01-{day:02d}",
            }
        )

    df = pd.DataFrame(rows)
    spec = FilterSpec(start_date="2024-01-01", end_date="2024-01-20", region_id="costa", sensor="MODIS")
    result = detect_anomalies(df, spec, threshold=2.0, window_days=3, min_observed=3, min_baseline=5, fdr_alpha=0.1)
    assert result["summary"]["flagged"] >= 1
    flagged_dates = {a["date"] for a in result["anomalies"]}
    assert "2024-01-10" in flagged_dates
    top = next(a for a in result["anomalies"] if a["date"] == "2024-01-10")
    assert top["direction"] == "high"
    assert top["observed"] == 20
    assert top["z_score"] > 2.0
