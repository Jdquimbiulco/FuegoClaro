from __future__ import annotations

import json

from app.domain.dtos import SusceptibilityMapDTO
from app.domain.models import FilterSpec
from app.services import environmental_alerts_service, protected_areas_service


def test_protected_areas_normalizes_and_intersects(monkeypatch, tmp_path):
    payload = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[[-79, -1], [-78, -1], [-78, 0], [-79, 0], [-79, -1]]]},
            "properties": {"csnap": "42", "nam": "Prueba", "map": "PARQUE", "subap": "SNAP"},
        }],
    }
    path = tmp_path / "protected_areas_snap_ec.geojson"
    path.write_text(json.dumps(payload), encoding="utf-8")
    protected_areas_service._catalog.cache_clear()
    monkeypatch.setattr(protected_areas_service, "get_settings", lambda: type("Settings", (), {"regions_dir": tmp_path})())

    result = protected_areas_service.geojson()
    match = protected_areas_service.intersecting_areas({"type": "Point", "coordinates": [-78.5, -0.5]})

    assert result["features"][0]["properties"]["name"] == "Prueba"
    assert match[0]["properties"]["area_id"] == "snap-42"
    protected_areas_service._catalog.cache_clear()


def test_predictive_alert_excludes_galapagos(monkeypatch):
    risk = SusceptibilityMapDTO(
        level="cell",
        features=[
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-79, -1], [-78, -1], [-78, 0], [-79, 0], [-79, -1]]]}, "properties": {"area_id": "main", "latitude": -0.5, "longitude": -78.5, "risk_level": "Extremo", "probability": 0.8, "region_id": "sierra", "prediction_date": "2026-11-14"}},
            {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[[-91, -1], [-90, -1], [-90, 0], [-91, 0], [-91, -1]]]}, "properties": {"area_id": "gal", "latitude": -0.5, "longitude": -90.5, "risk_level": "Extremo", "probability": 0.8, "region_id": "galapagos", "prediction_date": "2026-11-14"}},
        ],
    )
    area = {"properties": {"area_id": "snap-1", "name": "Reserva", "category": "PARQUE", "subsystem": "SNAP"}}
    monkeypatch.setattr(environmental_alerts_service.susceptibility_service, "get_map", lambda **_: risk)
    monkeypatch.setattr(environmental_alerts_service.protected_areas_service, "intersecting_areas", lambda _: [area])
    monkeypatch.setattr(environmental_alerts_service, "_observed_alerts", lambda _: [])

    payload = environmental_alerts_service.list_alerts(FilterSpec(start_date="2026-01-01", end_date="2026-01-02"))

    assert payload["summary"]["predictive"] == 1
    assert payload["alerts"][0]["risk"]["cell_id"] == "main"
