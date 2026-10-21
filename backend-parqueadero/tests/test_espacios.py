"""Creacion de los puestos del plano en lote. Requiere DATABASE_URL / SECRET_KEY en el entorno;
la base de pruebas la prepara conftest."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from tests.test_cupos import API, _espacio, _token, admin, client, zona  # noqa: E402,F401


def _codigos(client, admin, zona_id):
    return sorted(e["codigo"] for e in client.get(f"{API}/espacios", headers=admin, params={"zona_id": zona_id}).json())


def test_lote_crea_los_que_faltan_sin_duplicar(client, admin, zona):
    _espacio(client, admin, zona["id"], codigo="A-01")
    lote = {"zona_id": zona["id"], "codigos": ["a-01", "A-02", "B-01", "A-02"]}

    r = client.post(f"{API}/espacios/lote", headers=admin, json=lote)
    assert r.status_code == 200, r.text
    assert r.json() == {"creados": 2, "existentes": 1}
    assert _codigos(client, admin, zona["id"]) == ["A-01", "A-02", "B-01"]

    # Repetirlo no crea nada nuevo.
    assert client.post(f"{API}/espacios/lote", headers=admin, json=lote).json() == {"creados": 0, "existentes": 3}
    assert _codigos(client, admin, zona["id"]) == ["A-01", "A-02", "B-01"]


def test_lote_solo_admin_y_zona_existente(client, admin, zona):
    lote = {"zona_id": zona["id"], "codigos": ["A-01"]}
    assert client.post(f"{API}/espacios/lote", headers=_token("vigilante"), json=lote).status_code == 403
    assert client.post(f"{API}/espacios/lote", json=lote).status_code == 401

    otra = {"zona_id": str(uuid.uuid4()), "codigos": ["A-01"]}
    assert client.post(f"{API}/espacios/lote", headers=admin, json=otra).status_code == 404
    assert client.post(f"{API}/espacios/lote", headers=admin, json={**lote, "codigos": []}).status_code == 422
    assert client.post(f"{API}/espacios/lote", headers=admin, json={**lote, "codigos": ["X" * 21]}).status_code == 422
