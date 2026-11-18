"""Compensacion del cupo: si algo falla despues de mover el cupo en parqueadero, accesos lo deshace
y reintenta hasta 3 veces solo cuando parqueadero no responde. Las esperas entre intentos se anotan
en vez de dormir; los dobles de parqueadero e identidad vienen de test_accesos."""

import logging
import os

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402
from app.services import acceso_service, auditoria_service  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _accesos_abiertos,
    _entrada_visitante,
    admin,
    client,
    identidad,
    parqueadero,
)

DESFASE = "el contador quedo desfasado"


# Anota las esperas entre intentos en vez de dormir.
@pytest.fixture
def esperas(monkeypatch):
    anotadas = []
    monkeypatch.setattr(acceso_service.time, "sleep", anotadas.append)
    return anotadas


# Hace fallar la traza de auditoria, como si no se pudiera guardar el acceso.
def _auditoria_caida(monkeypatch):
    def caida(*args, **kwargs):
        raise RuntimeError("auditoria caida")

    monkeypatch.setattr(auditoria_service, "registrar_auditoria", caida)


# Liberar que falla como parqueadero caido las primeras ``fallos`` veces; devuelve los intentos.
def _liberar_que_falla(monkeypatch, fallos):
    intentos = []

    def liberar(zona_id, espacio_id):
        intentos.append(zona_id)
        if len(intentos) <= fallos:
            raise parqueadero_client.ParqueaderoNoDisponibleError("El servicio de parqueadero no esta disponible")

    monkeypatch.setattr(parqueadero_client, "liberar_cupo", liberar)
    return intentos


def test_la_liberacion_se_reintenta_y_funciona_a_la_tercera(admin, parqueadero, identidad, monkeypatch, esperas, caplog):
    vehiculo = identidad.vehiculo()
    _auditoria_caida(monkeypatch)
    intentos = _liberar_que_falla(monkeypatch, fallos=2)

    sin_excepciones = TestClient(app, raise_server_exceptions=False)
    assert _entrada_visitante(sin_excepciones, admin, vehiculo["id"]).status_code == 500
    assert parqueadero.movimientos == ["ocupar"]
    assert len(intentos) == 3
    assert esperas == [0.5, 1.0]
    assert DESFASE not in caplog.text
    assert _accesos_abiertos(vehiculo["id"]) == 0


def test_si_los_tres_intentos_fallan_queda_el_desfase_en_el_log(admin, parqueadero, identidad, monkeypatch, esperas, caplog):
    vehiculo = identidad.vehiculo()
    _auditoria_caida(monkeypatch)
    intentos = _liberar_que_falla(monkeypatch, fallos=3)

    sin_excepciones = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR):
        assert _entrada_visitante(sin_excepciones, admin, vehiculo["id"]).status_code == 500
    assert len(intentos) == 3
    assert esperas == [0.5, 1.0]
    assert f"tras 3 intentos: {DESFASE}" in caplog.text
    assert _accesos_abiertos(vehiculo["id"]) == 0


def test_si_volver_a_ocupar_da_409_no_se_reintenta(client, admin, parqueadero, identidad, monkeypatch, esperas, caplog):
    vehiculo = identidad.vehiculo()
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text
    acceso_id = r.json()["id"]

    intentos = []

    def ocupar_tomado(zona_id, espacio_id):
        intentos.append(zona_id)
        raise parqueadero_client.CupoNoDisponibleError("El espacio no esta libre en esta zona")

    monkeypatch.setattr(parqueadero_client, "ocupar_cupo", ocupar_tomado)
    _auditoria_caida(monkeypatch)

    sin_excepciones = TestClient(app, raise_server_exceptions=False)
    with caplog.at_level(logging.WARNING):
        assert sin_excepciones.post(f"/api/v1/accesos/{acceso_id}/salida", headers=admin).status_code == 500
    assert parqueadero.movimientos == ["ocupar", "liberar"]
    assert len(intentos) == 1
    assert esperas == []
    assert "rechazo la compensacion del cupo" in caplog.text and "con 409" in caplog.text
    assert _accesos_abiertos(vehiculo["id"]) == 1
