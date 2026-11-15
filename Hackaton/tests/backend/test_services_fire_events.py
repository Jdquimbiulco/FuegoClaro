from app.domain.dtos import FireEventDTO
from app.domain.models import FilterSpec
from app.services import fire_events_service


def _event(event_id: str, severity: str, province: str, frp: float) -> FireEventDTO:
    return FireEventDTO(
        id_evento=event_id,
        frp_total=frp,
        frp_max=frp,
        frp_medio=frp,
        puntos_count=1,
        geometria={"type": "Polygon", "coordinates": [[[-79.0, -4.0], [-78.9, -4.0], [-78.9, -3.9], [-79.0, -4.0]]]},
        centro=(-4.0, -79.0), inicio="2026-08-01", fin="2026-08-01", dias=["2026-08-01"],
        diurnas=1, nocturnas=0, sensores=["VIIRS"], provincias=[province], puntos_ids=[event_id],
        contraste_medio_k=10.0, nivel_alerta=severity, nivel_alerta_label=severity, motivo_regla="prueba", rank=1,
    )


def test_lista_filtra_ordena_y_pagina(monkeypatch):
    events = [_event("EVT-2", "quema_menor", "loja", 20), _event("EVT-1", "alerta_roja", "azuay", 10)]
    monkeypatch.setattr(fire_events_service, "_events_for", lambda spec: events)
    spec = FilterSpec(start_date="2026-08-01", end_date="2026-08-31", region_id="all", sensor="all")

    page, total = fire_events_service.list_events(spec, province_ids=["azuay"], limit=1)

    assert total == 1
    assert page[0].id_evento == "EVT-1"


def test_total_no_cambia_al_paginar(monkeypatch):
    events = [_event("EVT-1", "alerta_roja", "loja", 20), _event("EVT-2", "alerta_media", "loja", 10)]
    monkeypatch.setattr(fire_events_service, "_events_for", lambda spec: events)
    spec = FilterSpec(start_date="2026-08-01", end_date="2026-08-31", region_id="all", sensor="all")

    first, total_first = fire_events_service.list_events(spec, limit=1, offset=0)
    second, total_second = fire_events_service.list_events(spec, limit=1, offset=1)

    assert total_first == total_second == 2
    assert {first[0].id_evento, second[0].id_evento} == {"EVT-1", "EVT-2"}
