"""Creacion de los puestos del plano en lote. Requiere DATABASE_URL / SECRET_KEY en el entorno;
la base de pruebas la prepara conftest."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.services import realtime_service  # noqa: E402
from tests.test_cupos import API, _espacio, _token, admin, client, zona  # noqa: E402,F401


def _codigos(client, admin, zona_id):
    return sorted(e["codigo"] for e in client.get(f"{API}/espacios", headers=admin, params={"zona_id": zona_id}).json())


# Capacidad y cupos de la zona segun GET /zonas.
def _capacidad_y_cupos(client, admin, zona_id):
    zona = next(z for z in client.get(f"{API}/zonas", headers=admin).json() if z["id"] == zona_id)
    return zona["capacidad_total"], zona["cupos_disponibles"]


# Guarda los avisos por /ws/zonas en vez de enviarlos.
@pytest.fixture
def avisos(monkeypatch):
    enviados = []

    async def registrar(zona_id, cupos_disponibles):
        enviados.append((str(zona_id), cupos_disponibles))

    monkeypatch.setattr(realtime_service, "broadcast_actualizacion_zona", registrar)
    return enviados


def test_lote_crea_los_que_faltan_sin_duplicar(client, admin, zona):
    _espacio(client, admin, zona["id"], codigo="A-01")
    lote = {"zona_id": zona["id"], "codigos": ["a-01", "A-02", "B-01", "A-02"]}

    r = client.post(f"{API}/espacios/lote", headers=admin, json=lote)
    assert r.status_code == 200, r.text
    assert r.json() == {"creados": 2, "existentes": 1}
    assert _codigos(client, admin, zona["id"]) == ["A-01", "A-02", "B-01"]
    # La zona tenia capacidad 2 y ahora tiene 3 puestos: capacidad y cupos suben a 3.
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (3, 3)

    # Repetirlo no crea nada nuevo ni cambia la zona.
    assert client.post(f"{API}/espacios/lote", headers=admin, json=lote).json() == {"creados": 0, "existentes": 3}
    assert _codigos(client, admin, zona["id"]) == ["A-01", "A-02", "B-01"]
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (3, 3)


def test_lote_con_puesto_ocupado_conserva_el_descuento(client, admin, zona, avisos):
    espacio = _espacio(client, admin, zona["id"], codigo="A-01")
    assert client.post("/interno/cupos/ocupar", json={"zona_id": zona["id"], "espacio_id": espacio["id"]}).status_code == 200
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (2, 1)
    # Ocupar tambien avisa; solo interesan los avisos del lote.
    avisos.clear()

    lote = {"zona_id": zona["id"], "codigos": ["A-01", "A-02", "A-03", "A-04"]}
    assert client.post(f"{API}/espacios/lote", headers=admin, json=lote).json() == {"creados": 3, "existentes": 1}
    # La capacidad sube 2 (de 2 a 4) y los cupos tambien (de 1 a 3): A-01 sigue descontado.
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (4, 3)
    estados = {e["codigo"]: e["estado"] for e in client.get(f"{API}/espacios", headers=admin, params={"zona_id": zona["id"]}).json()}
    assert estados["A-01"] == "ocupado"
    assert avisos == [(zona["id"], 3)]

    # Repetirlo no cambia la zona ni avisa.
    assert client.post(f"{API}/espacios/lote", headers=admin, json=lote).json() == {"creados": 0, "existentes": 4}
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (4, 3)
    assert avisos == [(zona["id"], 3)]


def test_lote_no_baja_la_capacidad(client, admin, zona, avisos):
    # Un puesto nuevo en una zona de capacidad 2: responde 200, la zona queda igual y avisa igual.
    r = client.post(f"{API}/espacios/lote", headers=admin, json={"zona_id": zona["id"], "codigos": ["A-01"]})
    assert r.status_code == 200, r.text
    assert r.json() == {"creados": 1, "existentes": 0}
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (2, 2)
    assert avisos == [(zona["id"], 2)]

    # Con tantos puestos como capacidad tampoco cambia.
    assert client.post(f"{API}/espacios/lote", headers=admin, json={"zona_id": zona["id"], "codigos": ["A-02"]}).status_code == 200
    assert _capacidad_y_cupos(client, admin, zona["id"]) == (2, 2)
    assert len(avisos) == 2


def test_lote_solo_admin_y_zona_existente(client, admin, zona):
    lote = {"zona_id": zona["id"], "codigos": ["A-01"]}
    assert client.post(f"{API}/espacios/lote", headers=_token("vigilante"), json=lote).status_code == 403
    assert client.post(f"{API}/espacios/lote", json=lote).status_code == 401

    otra = {"zona_id": str(uuid.uuid4()), "codigos": ["A-01"]}
    assert client.post(f"{API}/espacios/lote", headers=admin, json=otra).status_code == 404
    assert client.post(f"{API}/espacios/lote", headers=admin, json={**lote, "codigos": []}).status_code == 422
    assert client.post(f"{API}/espacios/lote", headers=admin, json={**lote, "codigos": ["X" * 21]}).status_code == 422
