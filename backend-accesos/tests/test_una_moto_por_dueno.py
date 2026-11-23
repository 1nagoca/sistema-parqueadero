"""RN-12: una sola moto adentro por dueno, aunque tenga varias registradas. El dueno lo dice
identidad; los dobles de parqueadero e identidad vienen de test_accesos."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.identidad_client import client as identidad_client  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _accesos_abiertos,
    _entrada_visitante,
    admin,
    client,
    identidad,
    parqueadero,
)

API = settings.API_V1_PREFIX

# Mismo bloqueo que toma la entrada, pero sin esperar: True si lo consiguio.
INTENTAR_BLOQUEO = text("SELECT pg_try_advisory_xact_lock(hashtextextended(:clave, 0))")


def _moto(identidad, dueno):
    return identidad.vehiculo("UNA", propietario_estado="aprobado", propietario_id=dueno)


def _entrada(client, admin, vehiculo_id):
    return client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={"vehiculo_id": vehiculo_id, "zona_id": str(uuid.uuid4()), "espacio_id": str(uuid.uuid4())},
    )


def test_con_una_moto_adentro_la_otra_del_mismo_dueno_da_409_sin_tocar_el_cupo(client, admin, parqueadero, identidad):
    dueno = uuid.uuid4()
    a, b = _moto(identidad, dueno), _moto(identidad, dueno)
    assert _entrada(client, admin, a["id"]).status_code == 201

    r = _entrada(client, admin, b["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"El dueno ya tiene otra moto adentro ({a['placa']})"
    assert parqueadero.movimientos == ["ocupar"]  # solo la de A
    assert _accesos_abiertos(b["id"]) == 0


def test_cuando_sale_la_primera_entra_la_otra(client, admin, parqueadero, identidad):
    dueno = uuid.uuid4()
    a, b = _moto(identidad, dueno), _moto(identidad, dueno)
    acceso_a = _entrada(client, admin, a["id"]).json()
    assert _entrada(client, admin, b["id"]).status_code == 409

    assert client.post(f"{API}/accesos/{acceso_a['id']}/salida", headers=admin).status_code == 200
    r = _entrada(client, admin, b["id"])
    assert r.status_code == 201, r.text
    assert _accesos_abiertos(b["id"]) == 1


def test_motos_de_duenos_distintos_entran_las_dos(client, admin, parqueadero, identidad):
    a, b = _moto(identidad, uuid.uuid4()), _moto(identidad, uuid.uuid4())
    assert _entrada(client, admin, a["id"]).status_code == 201
    assert _entrada(client, admin, b["id"]).status_code == 201


def test_moto_sin_dueno_entra_aunque_haya_otras_adentro(client, admin, parqueadero, identidad):
    assert _entrada(client, admin, _moto(identidad, uuid.uuid4())["id"]).status_code == 201
    assert _entrada_visitante(client, admin, identidad.vehiculo()["id"]).status_code == 201
    r = _entrada_visitante(client, admin, identidad.vehiculo()["id"])
    assert r.status_code == 201, r.text


def test_identidad_caida_al_pedir_las_motos_del_dueno_da_503_sin_tocar_el_cupo(
    client, admin, parqueadero, identidad, monkeypatch
):
    dueno = uuid.uuid4()
    a, b = _moto(identidad, dueno), _moto(identidad, dueno)
    assert _entrada(client, admin, a["id"]).status_code == 201

    def caida(usuario_id):
        raise identidad_client.IdentidadNoDisponibleError("El servicio de identidad no esta disponible")

    monkeypatch.setattr(identidad_client, "vehiculos_de_usuario", caida)
    r = _entrada(client, admin, b["id"])
    assert r.status_code == 503, r.text
    assert parqueadero.movimientos == ["ocupar"]  # solo la de A
    assert _accesos_abiertos(b["id"]) == 0


def test_la_misma_moto_dos_veces_sigue_dando_el_409_de_siempre(client, admin, parqueadero, identidad):
    moto = _moto(identidad, uuid.uuid4())
    assert _entrada(client, admin, moto["id"]).status_code == 201

    r = _entrada(client, admin, moto["id"])
    assert r.status_code == 409
    assert r.json()["detail"] == "El vehiculo ya tiene un acceso activo"
    assert _accesos_abiertos(moto["id"]) == 1


def test_la_entrada_bloquea_al_dueno_hasta_el_commit(client, admin, parqueadero, identidad, monkeypatch):
    # Sin hilos: mientras la entrada ocupa el cupo ya tiene el bloqueo; otra sesion lo intenta sin esperar.
    dueno = uuid.uuid4()
    moto = _moto(identidad, dueno)
    intentos = {}

    def ocupar_y_probar(zona_id, espacio_id):
        with SessionLocal() as otra:
            intentos["mismo_dueno"] = otra.execute(INTENTAR_BLOQUEO, {"clave": str(dueno)}).scalar()
            intentos["otro_dueno"] = otra.execute(INTENTAR_BLOQUEO, {"clave": str(uuid.uuid4())}).scalar()
            otra.rollback()

    monkeypatch.setattr(parqueadero_client, "ocupar_cupo", ocupar_y_probar)
    assert _entrada(client, admin, moto["id"]).status_code == 201
    assert intentos == {"mismo_dueno": False, "otro_dueno": True}

    # tras el commit de la entrada, el bloqueo ya esta libre
    with SessionLocal() as otra:
        assert otra.execute(INTENTAR_BLOQUEO, {"clave": str(dueno)}).scalar() is True
        otra.rollback()
