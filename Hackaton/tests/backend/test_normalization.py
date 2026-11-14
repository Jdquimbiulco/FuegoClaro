import math
import pandas as pd

from app.domain.normalization import add_local_time, classify_confidence, normalize_chunk


def test_classify_confidence_modis_thresholds():
    assert classify_confidence(10, "MODIS") == ("low", 10.0)
    assert classify_confidence(30, "MODIS") == ("nominal", 30.0)
    assert classify_confidence(79, "MODIS") == ("nominal", 79.0)
    assert classify_confidence(80, "MODIS") == ("high", 80.0)


def test_classify_confidence_viirs_no_numeric_score():
    assert classify_confidence("l", "VIIRS") == ("low", None)
    assert classify_confidence("n", "VIIRS") == ("nominal", None)
    assert classify_confidence("h", "VIIRS") == ("high", None)
    assert classify_confidence("unknown", "VIIRS") == ("unknown", None)


def test_normalize_chunk_maps_fields_and_deterministic_id():
    raw = pd.DataFrame(
        {
            "latitude": [-0.1],
            "longitude": [-78.5],
            "acq_date": ["2024-01-02"],
            "acq_time": [615],
            "satellite": ["N20"],
            "instrument": ["VIIRS"],
            "confidence": ["n"],
            "bright_ti4": [330.5],
            "bright_ti5": [300.1],
            "frp": [12.3],
            "scan": [0.4],
            "track": [0.36],
            "version": ["2.0NRT"],
            "type": [0],
            "daynight": ["D"],
        }
    )
    out = normalize_chunk(raw, source_product="VIIRS_NOAA20_SP", sensor="VIIRS", provenance_id="prov1")
    assert len(out) == 1
    row = out.iloc[0]
    assert row["source_product"] == "VIIRS_NOAA20_SP"
    assert row["sensor"] == "VIIRS"
    assert row["satellite"] == "NOAA-20"
    assert row["acq_time"] == "0615"
    assert row["confidence_raw"] == "n"
    assert row["confidence_level"] == "nominal"
    assert row["confidence_score"] is None or (isinstance(row["confidence_score"], float) and math.isnan(row["confidence_score"]))
    assert row["brightness"] == 330.5
    assert row["bright_ti5"] == 300.1
    assert row["provenance_id"] == "prov1"
    assert isinstance(row["id"], str) and len(row["id"]) == 20

    out2 = normalize_chunk(raw, source_product="VIIRS_NOAA20_SP", sensor="VIIRS", provenance_id="prov2")
    assert out2.iloc[0]["id"] == row["id"]


def test_add_local_time_mainland_vs_galapagos():
    df = pd.DataFrame(
        {
            "acquired_at_utc": ["2024-01-01 03:30:00+00:00", "2024-01-01 03:30:00+00:00"],
            "region_id": ["sierra", "galapagos"],
        }
    )
    out = add_local_time(df)
    assert out.loc[0, "acq_date_local"] == "2023-12-31"
    assert out.loc[0, "acq_time_local"] == "22:30"
    assert out.loc[1, "acq_date_local"] == "2023-12-31"
    assert out.loc[1, "acq_time_local"] == "21:30"
