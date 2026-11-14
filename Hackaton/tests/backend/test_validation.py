import pandas as pd

from app.domain.validation import validate_detections


def _base_row(**overrides):
    row = {
        "id": "abc123",
        "latitude": -1.0,
        "longitude": -78.0,
        "acq_date": "2024-01-01",
        "acq_time": "1200",
        "sensor": "MODIS",
        "confidence_level": "nominal",
        "acquired_at_utc": "2024-01-01 12:00:00+00:00",
    }
    row.update(overrides)
    return row


def test_validate_detections_drops_invalid_and_duplicates():
    df = pd.DataFrame(
        [
            _base_row(id="ok1"),
            _base_row(id="ok1"),  # duplicate
            _base_row(id="badcoord", latitude=999.0),
            _base_row(id="zero", latitude=0.0, longitude=0.0),
            _base_row(id="baddate", acquired_at_utc="not-a-date"),
            _base_row(id="missing", latitude=None),
        ]
    )
    clean, report = validate_detections(df)
    assert report["input"] == 6
    assert report["dropped_duplicates"] == 1
    assert report["dropped_invalid_coords"] == 2
    assert report["dropped_invalid_datetime"] == 1
    assert report["dropped_missing_fields"] == 1
    assert report["valid"] == 1
    assert list(clean["id"]) == ["ok1"]
