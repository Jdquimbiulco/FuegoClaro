from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

DATASET = Path(__file__).resolve().parents[2] / "data" / "processed" / "detections.csv"


@pytest.fixture(scope="module")
def client():
    if not DATASET.exists():
        pytest.skip("No hay dataset procesado; ejecuta la ingesta para probar la API completa.")
    return TestClient(app)


def test_health_and_meta(client):
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    meta = client.get("/api/v1/meta")
    assert meta.status_code == 200
    payload = meta.json()
    assert payload["data_mode"] in {"real", "sample", "empty"}
    assert "regions" in payload and "provinces" in payload and "cantons" in payload
    assert len(payload["cantons"]) >= 220
    assert payload["date_range"]["start"] <= payload["date_range"]["end"]


def test_summary_and_detections_pagination(client):
    summary = client.get("/api/v1/stats/summary")
    assert summary.status_code == 200
    data = summary.json()["data"]
    assert data["total"] >= 0
    assert data["period"]["days"] >= 1

    page = client.get("/api/v1/detections", params={"limit": 2, "order": "desc"})
    assert page.status_code == 200
    payload = page.json()
    assert len(payload["data"]) <= 2
    assert payload["pagination"]["limit"] == 2
    assert payload["pagination"]["total"] >= len(payload["data"])


def test_geojson_and_analytics_endpoints(client):
    geojson = client.get("/api/v1/detections", params={"limit": 2, "format": "geojson"})
    assert geojson.status_code == 200
    assert geojson.json()["data"]["type"] == "FeatureCollection"

    comparison = client.get("/api/v1/comparison", params={"granularity": "month"})
    assert comparison.status_code == 200
    assert "by_sensor" in comparison.json()["data"]

    anomalies = client.get("/api/v1/anomalies", params={"threshold": 2.5})
    assert anomalies.status_code == 200
    assert "summary" in anomalies.json()["data"]

    insights = client.get("/api/v1/insights")
    assert insights.status_code == 200
    assert "insights" in insights.json()["data"]


def test_invalid_region_is_rejected(client):
    response = client.get("/api/v1/stats/summary", params={"region_id": "no-existe"})
    assert response.status_code == 400


def test_canton_filter_and_invalid_canton(client):
    meta = client.get("/api/v1/meta").json()
    canton_id = meta["cantons"][0]["id"]
    response = client.get("/api/v1/stats/summary", params={"canton_id": canton_id})
    assert response.status_code == 200
    assert response.json()["meta"]["filters"]["canton_id"] == canton_id

    invalid = client.get("/api/v1/stats/summary", params={"canton_id": "0000"})
    assert invalid.status_code == 400
