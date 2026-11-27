"""GET /accesos/mio: el estudiante ve donde estan sus motos adentro (placa, puesto y hora de
entrada) y nada mas. Sus motos las dice identidad; los dobles de parqueadero e identidad vienen
de test_accesos."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _id_del_token,
    _token,
    admin,
    client,
    identidad,
    parqueadero,
)

API = settings.API_V1_PREFIX


@pytest.fixture
def codigos(monkeypatch, parqueadero):
    """Parqueadero responde un codigo de puesto por cada espacio que se le pregunta."""
    nombres = {}

    def codigos_de_espacios(espacio_ids):
        return {espacio_id: nombres[espacio_id] for espacio_id in espacio_ids if espacio_id in nombres}

    monkeypatch.setattr(parqueadero_client, "codigos_de_espacios", codigos_de_espacios)
    return nombres


@pytest.fixture
def estudiante():
    return _token(rol="estudiante")


def _moto_adentro(client, admin, identidad, codigos, dueno_headers, codigo="B-12"):
    """Registra una moto aprobada del dueno de ese token y la entra en un puesto con ese codigo."""
    moto = identidad.vehiculo("MIA", propietario_estado="aprobado", propietario_id=_id_del_token(dueno_headers))
    espacio_id = uuid.uuid4()
    codigos[espacio_id] = codigo
    r = client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={"vehiculo_id": moto["id"], "zona_id": str(uuid.uuid4()), "espacio_id": str(espacio_id)},
    )
    assert r.status_code == 201, r.text
    return {**moto, "acceso": r.json()}


def test_el_estudiante_ve_su_moto_con_placa_puesto_y_hora_y_nada_mas(client, admin, identidad, codigos, estudiante):
    moto = _moto_adentro(client, admin, identidad, codigos, estudiante)

    r = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert r.status_code == 200, r.text
    assert r.json() == [
        {
            "placa": moto["placa"],
            "es_electrica": False,
            "numero_serie": None,
            "espacio_codigo": "B-12",
            "fecha_hora_entrada": moto["acceso"]["fecha_hora_entrada"],
        }
    ]


def test_no_ve_la_moto_de_otro_estudiante_que_esta_adentro(client, admin, identidad, codigos, estudiante):
    _moto_adentro(client, admin, identidad, codigos, _token(rol="estudiante"))

    r = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_sin_moto_adentro_da_lista_vacia_y_tras_la_salida_ya_no_sale(client, admin, identidad, codigos, estudiante):
    identidad.vehiculo("MIF", propietario_estado="aprobado", propietario_id=_id_del_token(estudiante))
    assert client.get(f"{API}/accesos/mio", headers=estudiante).json() == []  # tiene moto, pero afuera

    moto = _moto_adentro(client, admin, identidad, codigos, estudiante)
    assert [a["placa"] for a in client.get(f"{API}/accesos/mio", headers=estudiante).json()] == [moto["placa"]]

    assert client.post(f"{API}/accesos/{moto['acceso']['id']}/salida", headers=admin).status_code == 200
    r = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert r.status_code == 200 and r.json() == []


def test_con_dos_motos_suyas_adentro_de_antes_de_la_regla_salen_las_dos(client, admin, identidad, codigos, estudiante):
    # RN-12 ya no deja entrar la segunda por la API: va directo a la base, como un dato de antes de la regla.
    primera = _moto_adentro(client, admin, identidad, codigos, estudiante, codigo="A-01")
    segunda = identidad.vehiculo("MIA", propietario_estado="aprobado", propietario_id=_id_del_token(estudiante))
    espacio_id = uuid.uuid4()
    codigos[espacio_id] = "C-07"
    with SessionLocal() as db:
        db.add(Acceso(vehiculo_id=uuid.UUID(segunda["id"]), placa=segunda["placa"], zona_id=uuid.uuid4(), espacio_id=espacio_id))
        db.commit()

    r = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert r.status_code == 200, r.text
    assert [(a["placa"], a["espacio_codigo"]) for a in r.json()] == [
        (primera["placa"], "A-01"),
        (segunda["placa"], "C-07"),
    ]  # por hora de entrada


@pytest.mark.parametrize("rol", ["vigilante", "admin"])
def test_vigilante_y_admin_no_usan_esta_ruta(client, rol):
    assert client.get(f"{API}/accesos/mio", headers=_token(rol=rol)).status_code == 403


def test_sin_token_responde_401(client):
    assert client.get(f"{API}/accesos/mio").status_code == 401


def test_con_identidad_caida_responde_503(client, admin, identidad, codigos, estudiante):
    _moto_adentro(client, admin, identidad, codigos, estudiante)
    identidad.caida = True

    r = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert r.status_code == 503
    assert r.json()["detail"] == "El servicio de identidad no esta disponible"


def test_con_parqueadero_caido_sale_sin_codigo_de_puesto(client, admin, identidad, codigos, estudiante, monkeypatch):
    moto = _moto_adentro(client, admin, identidad, codigos, estudiante)

    def caido(espacio_ids):
        raise parqueadero_client.ParqueaderoNoDisponibleError("El servicio de parqueadero no esta disponible")

    monkeypatch.setattr(parqueadero_client, "codigos_de_espacios", caido)

    r = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert r.status_code == 200, r.text
    assert [(a["placa"], a["espacio_codigo"]) for a in r.json()] == [(moto["placa"], None)]
