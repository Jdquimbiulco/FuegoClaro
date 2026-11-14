import pandas as pd

from app.domain.fire_events import detect_fire_events, load_flare_sources


def _row(id: str, lat: float, lon: float, date: str, **overrides) -> dict:
    base = {
        "id": id,
        "sensor": "VIIRS",
        "latitude": lat,
        "longitude": lon,
        "acq_date_local": date,
        "daynight": "D",
        "frp": 5.0,
        "brightness": 330.0,
        "bright_ti5": 300.0,
        "confidence_level": "high",
        "province_id": "loja",
        "region_id": "sierra",
    }
    base.update(overrides)
    return base


def test_alerta_roja_por_frp_total_y_por_nocturna():
    rows = [
        _row("r1", -0.500, -78.000, "2024-08-01", frp=60.0),
        _row("r2", -0.505, -78.004, "2024-08-01", frp=60.0),
        _row("n1", -1.500, -77.500, "2024-08-01", frp=3.0, daynight="N"),
        _row("n2", -1.505, -77.504, "2024-08-01", frp=3.0, daynight="N"),
    ]
    events = detect_fire_events(pd.DataFrame(rows))
    assert len(events) == 2
    by_id = {e["puntos_ids"][0]: e for e in events}
    roja_frp = by_id["r1"]
    assert roja_frp["nivel_alerta"] == "alerta_roja"
    assert roja_frp["frp_total"] > 100
    assert roja_frp["motivo_regla"].startswith("FRP total")
    roja_night = by_id["n1"]
    assert roja_night["nivel_alerta"] == "alerta_roja"
    assert "nocturno" in roja_night["motivo_regla"]


def test_quema_menor_punto_individual_diurno_bajo_frp():
    events = detect_fire_events(pd.DataFrame([_row("solo", -0.5, -78.0, "2024-08-01", frp=2.0)]))
    assert len(events) == 1
    event = events[0]
    assert event["nivel_alerta"] == "quema_menor"
    assert event["puntos_count"] == 1
    assert event["frp_total"] < 10
    from shapely.geometry import shape
    assert shape(event["geometria"]).is_valid


def test_evento_colineal_genera_geometria_valida():
    from shapely.geometry import shape

    rows = [
        _row("l1", -0.500, -78.000, "2024-08-01", frp=6.0),
        _row("l2", -0.501, -78.001, "2024-08-01", frp=6.0),
        _row("l3", -0.502, -78.002, "2024-08-02", frp=6.0),
    ]
    events = detect_fire_events(pd.DataFrame(rows))
    assert len(events) == 1
    geom = events[0]["geometria"]
    assert geom["type"] == "Polygon"
    assert shape(geom).is_valid


def test_alerta_media_frp_moderado():
    rows = [
        _row("m1", -0.900, -78.800, "2024-08-01", frp=15.0),
        _row("m2", -0.905, -78.804, "2024-08-01", frp=15.0),
        _row("m3", -0.910, -78.808, "2024-08-01", frp=15.0),
    ]
    events = detect_fire_events(pd.DataFrame(rows))
    assert len(events) == 1
    event = events[0]
    assert event["nivel_alerta"] == "alerta_media"
    assert event["frp_total"] == 45.0
    assert event["puntos_count"] == 3


def test_metricas_y_geometria_convex_hull():
    rows = [
        _row("g1", -0.500, -78.000, "2024-08-01", frp=40.0),
        _row("g2", -0.506, -78.004, "2024-08-01", frp=40.0),
        _row("g3", -0.502, -78.002, "2024-08-02", frp=40.0),
        _row("g4", -0.504, -78.001, "2024-08-03", frp=20.0),
    ]
    events = detect_fire_events(pd.DataFrame(rows))
    assert len(events) == 1
    event = events[0]
    assert event["frp_total"] == 140.0
    assert event["frp_max"] == 40.0
    assert event["puntos_count"] == 4
    geom = event["geometria"]
    assert geom["type"] == "Polygon"
    ring = geom["coordinates"][0]
    assert ring[0] == ring[-1]
    assert event["nocturnas"] == 0
    assert event["dias"] == ["2024-08-01", "2024-08-02", "2024-08-03"]
    assert event["nivel_alerta"] == "alerta_roja"


def test_excluye_mecheros_por_coordenadas_fijas():
    sources = [{"name": "TestFlare", "lat": -0.133, "lon": -76.633}]
    rows = [
        _row("flare1", -0.134, -76.634, "2024-08-01", frp=50.0, daynight="N",
             province_id="orellana", region_id="amazonia"),
        _row("flare2", -0.140, -76.640, "2024-08-01", frp=50.0,
             province_id="orellana", region_id="amazonia"),
        _row("real1", -1.000, -77.000, "2024-08-01", frp=50.0),
        _row("real2", -1.005, -77.004, "2024-08-01", frp=50.0),
    ]
    events = detect_fire_events(pd.DataFrame(rows), flare_sources=sources, flare_radius_km=3.0)
    all_ids = [pid for e in events for pid in e["puntos_ids"]]
    assert "flare1" not in all_ids and "flare2" not in all_ids
    assert len(events) == 1
    assert set(events[0]["puntos_ids"]) == {"real1", "real2"}


def test_lista_mecheros_desde_archivo(tmp_path):
    import json

    path = tmp_path / "mecheros.json"
    path.write_text(json.dumps({"sources": [{"name": "Oficial", "lat": -0.2, "lon": -76.4}]}), encoding="utf-8")
    sources = load_flare_sources(path)
    assert sources == [{"name": "Oficial", "lat": -0.2, "lon": -76.4}]

    default_sources = load_flare_sources()
    assert any(s["name"] == "Shushufindi" for s in default_sources)


def test_ventana_temporal_48h():
    rows = [
        _row("t1", -0.700, -78.300, "2024-08-01", frp=20.0),
        _row("t2", -0.703, -78.303, "2024-08-03", frp=20.0),
        _row("t3", -0.706, -78.306, "2024-08-01", frp=20.0),
    ]
    events_48h = detect_fire_events(pd.DataFrame(rows), eps_days=2)
    assert len(events_48h) == 1
    events_24h = detect_fire_events(pd.DataFrame(rows), eps_days=1)
    assert len(events_24h) == 2
