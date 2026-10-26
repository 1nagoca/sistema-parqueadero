"""Horario del parqueadero (RN-11): fuera de 05:45-22:00 no se registra ninguna entrada (normal o
visitante) y las salidas se registran siempre. La hora la fija ``hora_fija`` de conftest; los
dobles de parqueadero e identidad vienen de test_accesos."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.core.config import settings  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _accesos_abiertos,
    _entrada_visitante,
    admin,
    client,
    identidad,
    parqueadero,
)

API = settings.API_V1_PREFIX
CERRADO = "El parqueadero esta cerrado: las entradas se registran de 05:45 a 22:00"


def _entrada_normal(client, admin, vehiculo_id):
    return client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={"vehiculo_id": vehiculo_id, "zona_id": str(uuid.uuid4()), "espacio_id": str(uuid.uuid4())},
    )


@pytest.mark.parametrize(("hora", "minuto"), [(5, 44), (22, 0)])
def test_fuera_de_horario_no_entra_nadie(client, admin, parqueadero, identidad, hora_fija, hora, minuto):
    visitante = identidad.vehiculo()
    moto = identidad.vehiculo(prefijo="MOT", propietario_estado="aprobado")
    hora_fija(hora, minuto)

    for r in (_entrada_visitante(client, admin, visitante["id"]), _entrada_normal(client, admin, moto["id"])):
        assert r.status_code == 409, r.text
        assert r.json()["detail"] == CERRADO

    assert parqueadero.movimientos == []  # no se toco el cupo
    assert _accesos_abiertos(visitante["id"]) == 0
    assert _accesos_abiertos(moto["id"]) == 0


@pytest.mark.parametrize(("hora", "minuto"), [(5, 45), (21, 59)])
def test_en_horario_se_registra_la_entrada(client, admin, parqueadero, identidad, hora_fija, hora, minuto):
    vehiculo = identidad.vehiculo()
    hora_fija(hora, minuto)
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text
    assert parqueadero.movimientos == ["ocupar"]


def test_la_salida_se_registra_aunque_este_cerrado(client, admin, parqueadero, identidad, hora_fija):
    vehiculo = identidad.vehiculo()
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text

    hora_fija(23)
    salida = client.post(f"{API}/accesos/{r.json()['id']}/salida", headers=admin)
    assert salida.status_code == 200, salida.text
    assert parqueadero.movimientos == ["ocupar", "liberar"]


def test_sin_restriccion_se_registra_a_las_23(client, admin, parqueadero, identidad, hora_fija, monkeypatch):
    vehiculo = identidad.vehiculo()
    monkeypatch.setattr(settings, "HORARIO_RESTRINGIDO", False)
    hora_fija(23)
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text


def test_el_horario_se_revisa_antes_que_identidad(client, admin, parqueadero, identidad, hora_fija):
    vehiculo = identidad.vehiculo()
    identidad.caida = True
    hora_fija(23)
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 409, r.text  # no 503: ni siquiera se pregunto a identidad
    assert r.json()["detail"] == CERRADO
    assert parqueadero.movimientos == []
