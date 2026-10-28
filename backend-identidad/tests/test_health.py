"""El servicio levanta y responde. Requiere DATABASE_URL / SECRET_KEY en el entorno; la base
de pruebas la prepara conftest."""

import logging
import os

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health_responde_ok():
    respuesta = TestClient(app).get("/health")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


def test_al_arrancar_avisa_en_la_consola_que_la_base_esta_conectada(caplog):
    caplog.set_level(logging.INFO)
    with TestClient(app):
        pass
    assert "Identidad: base de datos" in caplog.text and "conectada" in caplog.text
