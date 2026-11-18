"""RN-08: lista, busqueda, entrada y salida comprueban con identidad que el vigilante siga activo
(401 si esta dado de baja o no existe); si identidad no responde, se deja pasar con un aviso en el
log. Los dobles de parqueadero e identidad vienen de test_accesos."""

import logging
import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.identidad_client import client as identidad_client  # noqa: E402
from app.models.auditoria_acceso import AuditoriaAcceso  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _accesos_abiertos,
    _entrada_visitante,
    _token,
    admin,
    client,
    identidad,
    parqueadero,
)

API = settings.API_V1_PREFIX


# Trazas de auditoria que dejo ese usuario.
def _trazas_de(usuario_id):
    with SessionLocal() as db:
        return db.query(AuditoriaAcceso).filter(AuditoriaAcceso.realizado_por_id == uuid.UUID(usuario_id)).count()


def test_vigilante_activo_usa_las_cuatro_rutas(client, parqueadero, identidad):
    vigilante = _token(sub=identidad.usuario(rol="vigilante", activo=True))
    vehiculo = identidad.vehiculo()

    r = _entrada_visitante(client, vigilante, vehiculo["id"])
    assert r.status_code == 201, r.text
    acceso_id = r.json()["id"]
    assert acceso_id in [a["id"] for a in client.get(f"{API}/accesos", headers=vigilante).json()]
    assert client.get(f"{API}/accesos/buscar", headers=vigilante, params={"placa": vehiculo["placa"]}).json()["id"] == acceso_id
    assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=vigilante).status_code == 200
    assert parqueadero.movimientos == ["ocupar", "liberar"]


@pytest.mark.parametrize("caso", ["dado-de-baja", "no-existe"])
def test_vigilante_inactivo_o_inexistente_recibe_401_en_las_cuatro_rutas(client, admin, parqueadero, identidad, caso):
    if caso == "dado-de-baja":
        vigilante_id = identidad.usuario(rol="vigilante", activo=False)
    else:
        vigilante_id = str(uuid.uuid4())
        identidad.usuarios_inexistentes.add(uuid.UUID(vigilante_id))
    vigilante = _token(sub=vigilante_id)
    # una moto que ya estaba adentro, registrada por el admin
    adentro = identidad.vehiculo()
    r = _entrada_visitante(client, admin, adentro["id"])
    assert r.status_code == 201, r.text
    acceso_id = r.json()["id"]
    nuevo = identidad.vehiculo()

    respuestas = [
        client.get(f"{API}/accesos", headers=vigilante),
        client.get(f"{API}/accesos/buscar", headers=vigilante, params={"placa": adentro["placa"]}),
        _entrada_visitante(client, vigilante, nuevo["id"]),
        client.post(f"{API}/accesos/{acceso_id}/salida", headers=vigilante),
    ]
    assert [(x.status_code, x.json()["detail"]) for x in respuestas] == [(401, "Usuario inactivo")] * 4
    # ni entrada ni salida: el cupo solo se movio por el admin y no hay trazas del vigilante
    assert _accesos_abiertos(nuevo["id"]) == 0
    assert _accesos_abiertos(adentro["id"]) == 1
    assert parqueadero.movimientos == ["ocupar"]
    assert _trazas_de(vigilante_id) == 0


def test_con_identidad_caida_se_deja_pasar_con_un_aviso_y_la_entrada_da_503(client, admin, parqueadero, identidad, caplog):
    vigilante_id = identidad.usuario(rol="vigilante", activo=True)
    vigilante = _token(sub=vigilante_id)
    adentro = identidad.vehiculo()
    r = _entrada_visitante(client, admin, adentro["id"])
    assert r.status_code == 201, r.text
    acceso_id = r.json()["id"]
    nuevo = identidad.vehiculo()

    identidad.caida = True
    with caplog.at_level(logging.WARNING):
        assert acceso_id in [a["id"] for a in client.get(f"{API}/accesos", headers=vigilante).json()]
        r = client.get(f"{API}/accesos/buscar", headers=vigilante, params={"placa": adentro["placa"]})
        assert r.status_code == 200 and r.json()["id"] == acceso_id
        assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=vigilante).status_code == 200
        entrada = _entrada_visitante(client, vigilante, nuevo["id"])

    assert entrada.status_code == 503, entrada.text
    assert _accesos_abiertos(nuevo["id"]) == 0
    aviso = f"identidad no responde; no se comprobo si el usuario {vigilante_id} sigue activo"
    assert sum(aviso in m for m in caplog.messages) == 4


def test_mio_no_pregunta_si_el_estudiante_sigue_activo(client, identidad, monkeypatch):
    def no_debe_llamarse(usuario_id):
        raise AssertionError("GET /accesos/mio no comprueba si el estudiante sigue activo")

    monkeypatch.setattr(identidad_client, "obtener_usuario", no_debe_llamarse)
    r = client.get(f"{API}/accesos/mio", headers=_token(rol="estudiante"))
    assert r.status_code == 200, r.text
    assert r.json() == []
