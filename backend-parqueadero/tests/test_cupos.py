"""Zonas, espacios y cupos (RN-01 y RN-02). Requiere DATABASE_URL / SECRET_KEY en el entorno;
la base de pruebas la prepara conftest."""

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402

API = settings.API_V1_PREFIX


def _token(rol: str | None) -> dict:
    payload = {"sub": str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=5)}
    if rol is not None:
        payload["rol"] = rol
    return {"Authorization": f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')}"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin():
    return _token("admin")


@pytest.fixture
def zona(client, admin):
    r = client.post(
        f"{API}/zonas", headers=admin, json={"nombre": f"Zona {uuid.uuid4().hex[:8]}", "capacidad_total": 2}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _espacio(client, admin, zona_id, codigo="A1"):
    r = client.post(f"{API}/espacios", headers=admin, json={"zona_id": zona_id, "codigo": codigo})
    assert r.status_code == 201, r.text
    return r.json()


def _cupos(client, admin, zona_id):
    return next(z for z in client.get(f"{API}/zonas", headers=admin).json() if z["id"] == zona_id)[
        "cupos_disponibles"
    ]


def test_autenticacion_y_roles_salen_del_token(client, zona):
    assert client.get(f"{API}/zonas").status_code == 401
    assert client.get(f"{API}/zonas", headers=_token(None)).status_code == 401  # token sin rol
    assert client.get(f"{API}/zonas", headers=_token("estudiante")).status_code == 200

    nueva = {"nombre": f"Zona {uuid.uuid4().hex[:8]}", "capacidad_total": 3}
    assert client.post(f"{API}/zonas", headers=_token("vigilante"), json=nueva).status_code == 403
    assert client.get(f"{API}/reportes/ocupacion", headers=_token("vigilante")).status_code == 403


def test_ocupar_descuenta_hasta_agotar_y_liberar_devuelve(client, admin, zona):
    solicitud = {"zona_id": zona["id"]}

    assert client.post("/interno/cupos/ocupar", json=solicitud).json()["cupos_disponibles"] == 1
    assert client.post("/interno/cupos/ocupar", json=solicitud).json()["cupos_disponibles"] == 0
    assert client.post("/interno/cupos/ocupar", json=solicitud).status_code == 409  # RN-01
    assert _cupos(client, admin, zona["id"]) == 0

    assert client.post("/interno/cupos/liberar", json=solicitud).json()["cupos_disponibles"] == 1
    assert client.post("/interno/cupos/liberar", json=solicitud).json()["cupos_disponibles"] == 2
    assert client.post("/interno/cupos/liberar", json=solicitud).status_code == 409  # ya en capacidad total


def test_espacio_ocupado_no_descuenta_el_cupo(client, admin, zona):
    espacio = _espacio(client, admin, zona["id"])
    solicitud = {"zona_id": zona["id"], "espacio_id": espacio["id"]}

    assert client.post("/interno/cupos/ocupar", json=solicitud).status_code == 200
    # El espacio ya no esta libre: se rechaza y el cupo de la zona no se pierde.
    assert client.post("/interno/cupos/ocupar", json=solicitud).status_code == 409
    assert _cupos(client, admin, zona["id"]) == 1

    estados = {e["id"]: e["estado"] for e in client.get(f"{API}/espacios", headers=admin).json()}
    assert estados[espacio["id"]] == "ocupado"

    assert client.post("/interno/cupos/liberar", json=solicitud).status_code == 200
    estados = {e["id"]: e["estado"] for e in client.get(f"{API}/espacios", headers=admin).json()}
    assert estados[espacio["id"]] == "libre"

    codigos = client.get("/interno/espacios", params={"id": [espacio["id"]]}).json()
    assert codigos == [{"id": espacio["id"], "codigo": "A1"}]


def test_entradas_simultaneas_no_sobrevenden_cupos(client, zona):
    """RN-01 bajo concurrencia: 10 entradas a la vez sobre 2 cupos, solo 2 pasan."""
    solicitud = {"zona_id": zona["id"]}
    with ThreadPoolExecutor(max_workers=10) as hilos:
        codigos = list(
            hilos.map(lambda _: client.post("/interno/cupos/ocupar", json=solicitud).status_code, range(10))
        )
    assert codigos.count(200) == 2
    assert codigos.count(409) == 8
