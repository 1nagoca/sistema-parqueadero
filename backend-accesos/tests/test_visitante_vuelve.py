"""RN-03: una moto de visitante vuelve a entrar sin nueva autorizacion solo durante la hora
siguiente a su ultima salida; el acceso queda como visitante con la autorizacion anterior. Los
dobles de parqueadero e identidad vienen de test_accesos."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
from app.models.auditoria_acceso import AuditoriaAcceso  # noqa: E402
from app.models.enums import TipoAcceso  # noqa: E402
from test_accesos import (  # noqa: E402, F401
    _accesos_abiertos,
    _entrada_visitante,
    _id_del_token,
    admin,
    client,
    identidad,
    parqueadero,
)

API = settings.API_V1_PREFIX
SIN_AUTORIZACION = (
    "La moto de visitante necesita una nueva autorizacion: salio hace mas de 1 hora o no tiene una autorizacion previa"
)


def _entrada_normal(client, admin, vehiculo_id):
    return client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={"vehiculo_id": vehiculo_id, "zona_id": str(uuid.uuid4()), "espacio_id": str(uuid.uuid4())},
    )


def _entra_y_sale_hace(client, admin, vehiculo_id, minutos):
    # Entra como visitante, sale y corre su salida N minutos atras (y la entrada 10 antes); devuelve el acceso cerrado.
    acceso = _entrada_visitante(client, admin, vehiculo_id).json()
    assert client.post(f"{API}/accesos/{acceso['id']}/salida", headers=admin).status_code == 200
    with SessionLocal() as db:
        db.execute(
            text(
                "UPDATE accesos SET fecha_hora_entrada = now() - make_interval(mins => :m + 10),"
                " fecha_hora_salida = now() - make_interval(mins => :m) WHERE id = :id"
            ),
            {"m": minutos, "id": acceso["id"]},
        )
        db.commit()
    return acceso


def _traza_de_creacion(acceso_id):
    with SessionLocal() as db:
        return (
            db.query(AuditoriaAcceso)
            .filter(AuditoriaAcceso.registro_id == uuid.UUID(acceso_id), AuditoriaAcceso.accion == "creacion")
            .one()
        )


def test_vuelve_a_los_59_min_entra_como_visitante_con_la_autorizacion_anterior(client, admin, parqueadero, identidad):
    moto = identidad.vehiculo()
    anterior = _entra_y_sale_hace(client, admin, moto["id"], 59)

    r = _entrada_normal(client, admin, moto["id"])
    assert r.status_code == 201, r.text
    nuevo = r.json()
    assert nuevo["tipo_acceso"] == "visitante"
    assert nuevo["autorizado_por_id"] == _id_del_token(admin)
    assert nuevo["justificacion"] == "Visita a decanatura"
    assert _traza_de_creacion(nuevo["id"]).valores_nuevos["reingreso_de"] == anterior["id"]


def test_vuelve_a_los_61_min_da_409_sin_tocar_el_cupo(client, admin, parqueadero, identidad):
    moto = identidad.vehiculo()
    _entra_y_sale_hace(client, admin, moto["id"], 61)

    r = _entrada_normal(client, admin, moto["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == SIN_AUTORIZACION
    assert parqueadero.movimientos == ["ocupar", "liberar"]  # solo la entrada y la salida anteriores
    assert _accesos_abiertos(moto["id"]) == 0


def test_moto_de_visitante_que_nunca_entro_da_409(client, admin, parqueadero, identidad):
    moto = identidad.vehiculo()
    r = _entrada_normal(client, admin, moto["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == SIN_AUTORIZACION
    assert parqueadero.movimientos == []


def test_si_su_ultimo_acceso_fue_normal_da_409(client, admin, parqueadero, identidad):
    # como los reingresos de antes de esta regla: acceso normal cerrado hace 5 minutos
    moto = identidad.vehiculo()
    with SessionLocal() as db:
        db.add(Acceso(vehiculo_id=uuid.UUID(moto["id"]), placa=moto["placa"], zona_id=uuid.uuid4(), tipo_acceso=TipoAcceso.NORMAL))
        db.commit()
        db.execute(
            text(
                "UPDATE accesos SET fecha_hora_entrada = now() - interval '15 minutes',"
                " fecha_hora_salida = now() - interval '5 minutes' WHERE vehiculo_id = :v"
            ),
            {"v": moto["id"]},
        )
        db.commit()

    r = _entrada_normal(client, admin, moto["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == SIN_AUTORIZACION


def test_con_autorizacion_nueva_entra_aunque_haya_pasado_la_hora(client, admin, parqueadero, identidad):
    moto = identidad.vehiculo()
    _entra_y_sale_hace(client, admin, moto["id"], 61)

    r = _entrada_visitante(client, admin, moto["id"])
    assert r.status_code == 201, r.text
    assert r.json()["tipo_acceso"] == "visitante"
    assert "reingreso_de" not in _traza_de_creacion(r.json()["id"]).valores_nuevos


def test_moto_con_dueno_no_cambia(client, admin, parqueadero, identidad):
    moto = identidad.vehiculo("DUE", propietario_estado="aprobado")
    r = _entrada_normal(client, admin, moto["id"])
    assert r.status_code == 201, r.text
    assert r.json()["tipo_acceso"] == "normal"
    assert "reingreso_de" not in _traza_de_creacion(r.json()["id"]).valores_nuevos
