"""Memory regressions: preserve values while avoiding whole-payload copies."""
import asyncio
import json
from pathlib import Path


def test_lifespan_does_not_force_reload(monkeypatch):
    from app import main
    from app.services.data_store import get_store
    store = get_store()
    calls = []
    original = store.refresh
    def refresh(force=False):
        calls.append(force)
        return original(force=force)
    monkeypatch.setattr(store, "refresh", refresh)
    async def run():
        async with main.lifespan(main.app):
            pass
    asyncio.run(run())
    assert not any(calls), "An initialized store must not be loaded twice at startup"


def test_evidence_does_not_materialize_all_reason_records(monkeypatch):
    import pandas as pd
    from app.domain.fire_evidence import annotate_fire_evidence
    frame = pd.DataFrame({"id": ["x", "y"], "latitude": [0., 0.], "longitude": [-78., -78.],
                          "sensor": ["MODIS", "VIIRS"], "acq_date_local": ["2024-01-01"] * 2})
    original = frame.copy(deep=True)
    def no_records(*args, **kwargs):
        raise AssertionError("Do not materialize one dictionary per dataset row")
    monkeypatch.setattr(pd.DataFrame, "to_dict", no_records)
    result = annotate_fire_evidence(frame)
    assert len(result) == 2
    assert result["evidence_score"].notna().all()
    pd.testing.assert_frame_equal(frame, original)


def test_detection_serialization_is_batched(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    from app.api.v1.endpoints import detections
    original = detections.records
    def bounded_records(frame):
        assert len(frame) <= 256, "A response must not allocate all map points as dicts at once"
        return original(frame)
    monkeypatch.setattr(detections, "records", bounded_records)
    response = TestClient(app).get("/api/v1/detections?limit=20000&format=geojson&start_date=2022-01-01&end_date=2026-11-12")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]["features"]) == payload["pagination"]["returned"]
    assert payload["pagination"]["returned"] == 20000


def test_snap_stream_preserves_geometry_without_whole_file_read(monkeypatch, tmp_path):
    from app.services import protected_areas_service as snap
    from app.utils.json_safe import json_safe
    feature = {"type": "Feature", "properties": {"csnap": "01", "nam": "Área ñ"},
               "geometry": {"type": "Polygon", "coordinates": [[[-79.123456789, -1], [-78, -1], [-78, 0], [-79.123456789, -1]]]}}
    path = tmp_path / "protected_areas_snap_ec.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
    monkeypatch.setattr(snap, "_path", lambda: path)
    snap._catalog.cache_clear()
    def no_full_read(*args, **kwargs):
        raise AssertionError("SNAP must be parsed incrementally")
    monkeypatch.setattr(Path, "read_text", no_full_read)
    try:
        actual = snap.geojson()
        assert actual["features"][0]["geometry"] == feature["geometry"]
        streamed = json.loads(b"".join(snap.stream_response()))
        assert streamed["data"]["features"] == json_safe(actual["features"])
        assert streamed["meta"]["notes"] == actual["notes"]
        assert streamed["meta"]["module"]["areas"] == 1
    finally:
        snap._catalog.cache_clear()
