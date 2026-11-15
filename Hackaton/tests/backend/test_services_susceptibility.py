import pytest

from app.core.errors import InputValidationError
from app.services import susceptibility_service


def test_map_sin_artefacto_queda_pending(monkeypatch, tmp_path):
    settings = type("Settings", (), {"processed_dir": tmp_path})()
    monkeypatch.setattr(susceptibility_service, "get_settings", lambda: settings)

    result = susceptibility_service.get_map()

    assert result.type == "FeatureCollection"
    assert result.features == []
    assert result.summary["by_risk"]["Extremo"] == 0


def test_punto_fuera_de_ecuador_es_invalido():
    with pytest.raises(InputValidationError) as exc:
        susceptibility_service.predict_point(latitude=8.0, longitude=-79.5, when="2026-11-20")

    assert exc.value.status_code == 422
    assert exc.value.code == "VALIDATION_ERROR"
