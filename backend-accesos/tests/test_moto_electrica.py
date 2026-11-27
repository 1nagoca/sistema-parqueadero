"""Moto electrica en accesos (punto 7): no tiene placa, entra con su numero de serie copiado de
identidad, se busca por serial y sale como las demas. Los dobles de parqueadero e identidad
vienen de test_accesos."""

import logging
import os
import random
import string
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.identidad_client import client as identidad_client  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
from app.models.enums import TipoAcceso  # noqa: E402
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
NO_VERIFICADOS = "El vehiculo o su propietario aun no estan verificados por el administrador"


def _electrica(identidad, *, dueno=None, estado="aprobado", dueno_estado="aprobado", dueno_activo=True):
    """Registra en el doble de identidad una moto electrica de un estudiante; devuelve id, serial y dueno."""
    serie = "EB-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    vehiculo = identidad_client.VehiculoIdentidad(
        id=uuid.uuid4(),
        placa=None,
        es_visitante=False,
        estado_verificacion=estado,
        propietario_id=dueno or uuid.uuid4(),
        propietario_estado_verificacion=dueno_estado,
        propietario_activo=dueno_activo,
        es_electrica=True,
        numero_serie=serie,
    )
    identidad.vehiculos[vehiculo.id] = vehiculo
    return {"id": str(vehiculo.id), "serie": serie, "dueno": vehiculo.propietario_id}


def _entrada(client, admin, vehiculo_id):
    return client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={"vehiculo_id": vehiculo_id, "zona_id": str(uuid.uuid4()), "espacio_id": str(uuid.uuid4())},
    )


def _buscar(client, admin, **parametros):
    return client.get(f"{API}/accesos/buscar", headers=admin, params=parametros)


def test_la_entrada_guarda_placa_null_es_electrica_y_serial(client, admin, parqueadero, identidad, caplog):
    moto = _electrica(identidad)
    with caplog.at_level(logging.INFO, logger="app.services.acceso_service"):
        r = _entrada(client, admin, moto["id"])
    assert r.status_code == 201, r.text
    assert parqueadero.movimientos == ["ocupar"]
    with SessionLocal() as db:
        acceso = db.get(Acceso, uuid.UUID(r.json()["id"]))
        assert acceso.placa is None
        assert acceso.es_electrica is True
        assert acceso.numero_serie == moto["serie"]
    assert f"entrada registrada de la moto eléctrica {moto['serie']} (normal)" in caplog.text


def test_buscar_por_serial_con_espacios_minusculas_y_sin_guion(client, admin, parqueadero, identidad):
    moto = _electrica(identidad)
    acceso_id = _entrada(client, admin, moto["id"]).json()["id"]
    serie = moto["serie"]
    for consulta in (serie, serie.lower(), serie.replace("-", ""), f" {serie[:5]} {serie[5:]} "):
        r = _buscar(client, admin, numero_serie=consulta)
        assert r.status_code == 200, (consulta, r.text)
        assert r.json()["id"] == acceso_id


def test_buscar_exige_placa_o_serial_y_solo_uno(client, admin, parqueadero, identidad):
    for parametros in ({}, {"placa": "ABC12D", "numero_serie": "EB12345678"}):
        r = _buscar(client, admin, **parametros)
        assert r.status_code == 422, (parametros, r.text)
        assert r.json()["detail"] == "Indica la placa o el número de serie, solo uno de los dos"


def test_serial_sin_acceso_abierto_da_su_404(client, admin, parqueadero, identidad):
    r = _buscar(client, admin, numero_serie="EB-NOESTA12")
    assert r.status_code == 404
    assert r.json()["detail"] == "No hay un acceso activo para ese número de serie"
    # la placa sigue con su propio mensaje
    r = _buscar(client, admin, placa="ZZZ99Z")
    assert r.status_code == 404 and r.json()["detail"] == "No hay un acceso activo para esa placa"


def test_vehiculos_adentro_y_mio_traen_placa_null_y_serial(client, admin, parqueadero, identidad):
    moto = _electrica(identidad)
    r = _entrada(client, admin, moto["id"])
    assert r.status_code == 201, r.text

    activos = {a["id"]: a for a in client.get(f"{API}/accesos", headers=admin).json()}
    activo = activos[r.json()["id"]]
    assert activo["placa"] is None and activo["es_electrica"] is True and activo["numero_serie"] == moto["serie"]

    estudiante = _token(rol="estudiante", sub=str(moto["dueno"]))
    mio = client.get(f"{API}/accesos/mio", headers=estudiante)
    assert mio.status_code == 200, mio.text
    assert mio.json() == [
        {
            "placa": None,
            "es_electrica": True,
            "numero_serie": moto["serie"],
            "espacio_codigo": None,
            "fecha_hora_entrada": r.json()["fecha_hora_entrada"],
        }
    ]


def test_otra_moto_del_dueno_adentro_dice_moto_electrica_y_su_serial(client, admin, parqueadero, identidad):
    moto = _electrica(identidad)
    assert _entrada(client, admin, moto["id"]).status_code == 201
    otra = identidad.vehiculo("OTR", propietario_estado="aprobado", propietario_id=moto["dueno"])

    r = _entrada(client, admin, otra["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == f"El dueno ya tiene otra moto adentro (moto eléctrica {moto['serie']})"
    assert parqueadero.movimientos == ["ocupar"]


@pytest.mark.parametrize(
    "campos, mensaje",
    [
        ({"estado": "pendiente"}, NO_VERIFICADOS),
        ({"estado": "rechazado"}, NO_VERIFICADOS),
        ({"dueno_estado": "pendiente"}, NO_VERIFICADOS),
        ({"dueno_activo": False}, "El propietario de la moto esta dado de baja"),
    ],
)
def test_electrica_sin_aprobar_o_con_dueno_de_baja_da_el_mismo_409(client, admin, parqueadero, identidad, campos, mensaje):
    moto = _electrica(identidad, **campos)
    r = _entrada(client, admin, moto["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == mensaje
    assert parqueadero.movimientos == [] and _accesos_abiertos(moto["id"]) == 0


def test_electrica_como_visitante_se_rechaza_sin_tocar_el_cupo(client, admin, parqueadero, identidad):
    moto = _electrica(identidad)
    r = _entrada_visitante(client, admin, moto["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "La moto eléctrica solo entra como acceso normal: es de un estudiante registrado"
    assert parqueadero.movimientos == [] and _accesos_abiertos(moto["id"]) == 0


def test_la_salida_es_como_la_de_las_demas(client, admin, parqueadero, identidad, caplog):
    moto = _electrica(identidad)
    acceso_id = _entrada(client, admin, moto["id"]).json()["id"]
    with caplog.at_level(logging.INFO, logger="app.services.acceso_service"):
        r = client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin)
    assert r.status_code == 200, r.text
    assert parqueadero.movimientos == ["ocupar", "liberar"]
    assert f"salida registrada de la moto eléctrica {moto['serie']}" in caplog.text
    assert _buscar(client, admin, numero_serie=moto["serie"]).status_code == 404


def test_la_traza_de_su_entrada_no_da_500(client, admin, parqueadero, identidad):
    moto = _electrica(identidad)
    acceso_id = _entrada(client, admin, moto["id"]).json()["id"]
    r = client.get(f"{API}/auditoria", headers=admin, params={"tabla_afectada": "accesos", "por_pagina": 200})
    assert r.status_code == 200, r.text
    (traza,) = [t for t in r.json()["items"] if t["registro_id"] == acceso_id]
    # hasta la E5 el detalle de la electrica sale vacio y el frontend la muestra en JSON
    assert traza["detalle"] is None


@pytest.mark.parametrize(
    "campos",
    [
        {"es_electrica": True, "placa": "ABC12D", "numero_serie": "EB12345678"},  # electrica con placa
        {"es_electrica": True, "placa": None, "numero_serie": None},  # electrica sin serial
        {"es_electrica": False, "placa": None, "numero_serie": None},  # moto sin placa
        {"es_electrica": True, "placa": None, "numero_serie": "eb12345678"},  # serial en minusculas
        {"es_electrica": True, "placa": None, "numero_serie": "EB12345678", "tipo_acceso": TipoAcceso.VISITANTE},
    ],
)
def test_la_base_rechaza_combinaciones_invalidas(campos):
    extra = {}
    if campos.get("tipo_acceso") == TipoAcceso.VISITANTE:
        extra = {"autorizado_por_id": uuid.uuid4(), "justificacion": "Prueba"}
    with SessionLocal() as db:
        db.add(Acceso(vehiculo_id=uuid.uuid4(), zona_id=uuid.uuid4(), **campos, **extra))
        with pytest.raises(IntegrityError):
            db.commit()
