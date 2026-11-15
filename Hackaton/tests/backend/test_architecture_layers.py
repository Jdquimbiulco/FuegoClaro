from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "backend" / "app"


def test_controladores_nuevos_no_calculan_con_pandas_ni_dominio():
    source = (ROOT / "api" / "v1" / "endpoints" / "fire_events.py").read_text(encoding="utf-8")
    assert "import pandas" not in source
    assert "app.domain.fire_events" not in source
    assert "app.ml" not in source


def test_servicios_nuevos_no_importan_fastapi_ni_http_exception():
    for path in (ROOT / "services").glob("*_service.py"):
        source = path.read_text(encoding="utf-8")
        assert "import fastapi" not in source
        assert "HTTPException" not in source
