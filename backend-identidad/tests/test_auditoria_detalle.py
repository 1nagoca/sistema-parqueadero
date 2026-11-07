"""GET /verificaciones/auditoria agrega a cada traza un detalle (el usuario, o la placa y el dueno del
vehiculo) y el nombre de quien la hizo, leidos con LEFT JOIN en la consulta de la pagina. Solo
nombre, rol y placa (Ley 1581). Los ayudantes vienen de test_verificacion."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from sqlalchemy import event  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.auditoria_identidad import AuditoriaIdentidad  # noqa: E402
from app.models.enums import AccionAuditoria, RolUsuario, TipoVehiculo  # noqa: E402
from app.models.vehiculo import Vehiculo  # noqa: E402
from tests.test_verificacion import (  # noqa: E402, F401
    PNG,
    _login,
    _personal,
    _placa,
    _registrar,
    _vehiculo,
    carpeta_uploads,
    client,
    sufijo,
)

API = settings.API_V1_PREFIX
CAMPOS = {
    "id", "tabla_afectada", "registro_id", "accion", "valores_anteriores", "valores_nuevos",
    "realizado_por_id", "motivo", "fecha_hora", "ip_origen", "detalle", "realizado_por_nombre",
}
ESTUDIANTE = {"nombre": "Estudiante Prueba", "rol": "estudiante", "placa": None}


def _trazas_de(client, admin, registro_id, **params):
    """Trazas de ese registro en la primera pagina (las mas nuevas), de la mas vieja a la mas nueva."""
    r = client.get(f"{API}/verificaciones/auditoria", headers=admin, params={"por_pagina": 200, **params})
    assert r.status_code == 200, r.text
    return [t for t in reversed(r.json()["items"]) if t["registro_id"] == str(registro_id)]


def _estudiante_con_carnet_y_vehiculo(client, sufijo):
    """Como el de test_verificacion, pero con una placa del todo al azar para no chocar en la corrida."""
    assert _registrar(client, sufijo).status_code == 201
    est = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")
    uid = client.get(f"{API}/usuarios/me", headers=est).json()["id"]
    r = client.post(f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    r = _vehiculo(client, est, _placa())
    assert r.status_code == 201, r.text
    return est, uid, r.json()["id"]


def _placa_de(vehiculo_id):
    with SessionLocal() as db:
        return db.get(Vehiculo, uuid.UUID(vehiculo_id)).placa


def _insertar_trazas(*trazas):
    """Solo INSERT: la auditoria es append-only."""
    with SessionLocal() as db:
        filas = [AuditoriaIdentidad(accion=AccionAuditoria.ACTUALIZACION, **t) for t in trazas]
        db.add_all(filas)
        db.commit()
        return [str(f.id) for f in filas]


def test_rechazar_y_aprobar_al_estudiante_y_su_moto_traen_quien_y_que(client, sufijo):
    _, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    _, uid, vehiculo_id = _estudiante_con_carnet_y_vehiculo(client, sufijo)
    resolver = f"{API}/verificaciones/usuarios/{uid}/resolver"
    assert client.post(resolver, headers=admin, json={"aprobar": False, "motivo": "Carnet ilegible"}).status_code == 200
    assert client.post(resolver, headers=admin, json={"aprobar": True}).status_code == 200
    r = client.post(f"{API}/verificaciones/vehiculos/{vehiculo_id}/resolver", headers=admin, json={"aprobar": True})
    assert r.status_code == 200, r.text

    rechazo, aprobacion = _trazas_de(client, admin, uid)
    assert set(rechazo) == CAMPOS
    for traza in (rechazo, aprobacion):
        assert traza["detalle"] == ESTUDIANTE
        assert traza["realizado_por_nombre"] == "Admin Prueba"
    # lo guardado no cambia
    assert rechazo["valores_nuevos"] == {"estado_verificacion": "rechazado"} and rechazo["motivo"] == "Carnet ilegible"

    (moto,) = _trazas_de(client, admin, vehiculo_id)
    assert moto["detalle"] == {"nombre": "Estudiante Prueba", "rol": "estudiante", "placa": _placa_de(vehiculo_id)}
    assert moto["realizado_por_nombre"] == "Admin Prueba"


def test_moto_de_visitante_sin_dueno_trae_la_placa_sin_nombre(client, sufijo):
    admin_id, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    with SessionLocal() as db:
        visitante = Vehiculo(placa=_placa(), tipo_vehiculo=TipoVehiculo.MOTO, es_visitante=True)
        db.add(visitante)
        db.commit()
        vehiculo_id, placa = visitante.id, visitante.placa
    # ningun flujo deja traza de un visitante: se arma a mano
    _insertar_trazas(dict(tabla_afectada="vehiculos", registro_id=vehiculo_id, realizado_por_id=uuid.UUID(admin_id)))

    (traza,) = _trazas_de(client, admin, vehiculo_id)
    assert traza["detalle"] == {"nombre": None, "rol": None, "placa": placa}
    assert traza["realizado_por_nombre"] == "Admin Prueba"


def test_baja_y_reactivacion_del_estudiante_traen_al_estudiante_y_su_moto(client, sufijo):
    _, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    _, uid, vehiculo_id = _estudiante_con_carnet_y_vehiculo(client, sufijo)
    client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": True})
    client.post(f"{API}/verificaciones/vehiculos/{vehiculo_id}/resolver", headers=admin, json={"aprobar": True})
    assert client.post(f"{API}/usuarios/{uid}/desactivar", headers=admin, json={"motivo": "Se retiro"}).status_code == 200
    assert client.post(f"{API}/usuarios/{uid}/reactivar", headers=admin).status_code == 200

    _, baja, reactivacion = _trazas_de(client, admin, uid)
    assert baja["valores_nuevos"] == {"activo": False} and baja["motivo"] == "Se retiro"
    assert reactivacion["valores_nuevos"] == {"activo": True, "estado_verificacion": "pendiente"}
    for traza in (baja, reactivacion):
        assert traza["detalle"] == ESTUDIANTE and traza["realizado_por_nombre"] == "Admin Prueba"

    _, rechazada = _trazas_de(client, admin, vehiculo_id)
    assert rechazada["valores_nuevos"] == {"estado_verificacion": "rechazado"}
    assert rechazada["detalle"] == {"nombre": "Estudiante Prueba", "rol": "estudiante", "placa": _placa_de(vehiculo_id)}


def test_vigilante_dado_de_baja_trae_su_rol(client, sufijo):
    _, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    vigilante_id, _ = _personal(client, RolUsuario.VIGILANTE, sufijo)
    r = client.post(f"{API}/usuarios/{vigilante_id}/desactivar", headers=admin, json={"motivo": "Renuncio"})
    assert r.status_code == 200, r.text

    (traza,) = _trazas_de(client, admin, vigilante_id)
    assert traza["detalle"] == {"nombre": "Vigilante Prueba", "rol": "vigilante", "placa": None}


def test_traza_sin_registro_trae_detalle_null_y_el_autor(client, sufijo):
    admin_id, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    al_azar = uuid.uuid4()
    (traza_id,) = _insertar_trazas(
        dict(
            tabla_afectada="usuarios", registro_id=al_azar, realizado_por_id=uuid.UUID(admin_id),
            valores_nuevos={"activo": False}, motivo="Prueba",
        )
    )

    (traza,) = _trazas_de(client, admin, al_azar)
    assert traza["id"] == traza_id and traza["detalle"] is None
    assert traza["realizado_por_nombre"] == "Admin Prueba"
    assert traza["valores_nuevos"] == {"activo": False} and traza["motivo"] == "Prueba"
    assert traza["realizado_por_id"] == admin_id


def test_una_pagina_de_50_hace_las_mismas_consultas_que_una_de_1(client, sufijo):
    admin_id, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    _, uid, vehiculo_id = _estudiante_con_carnet_y_vehiculo(client, sufijo)
    autor = uuid.UUID(admin_id)
    _insertar_trazas(
        *[dict(tabla_afectada="usuarios", registro_id=uuid.UUID(uid), realizado_por_id=autor) for _ in range(30)],
        *[dict(tabla_afectada="vehiculos", registro_id=uuid.UUID(vehiculo_id), realizado_por_id=autor) for _ in range(30)],
    )

    consultas = []

    def contar(conn, cursor, sentencia, parametros, contexto, varias):
        consultas.append(sentencia)

    def consultas_de(por_pagina):
        consultas.clear()
        event.listen(engine, "before_cursor_execute", contar)
        try:
            r = client.get(f"{API}/verificaciones/auditoria", headers=admin, params={"por_pagina": por_pagina})
        finally:
            event.remove(engine, "before_cursor_execute", contar)
        assert r.status_code == 200, r.text
        return len(consultas), r.json()["items"]

    una, _ = consultas_de(1)
    cincuenta, items = consultas_de(50)
    assert len(items) == 50
    assert una > 0 and cincuenta == una  # el contador si ve las consultas
    # las 50 mas nuevas son las insertadas: todas con detalle y autor
    assert all(t["detalle"] is not None and t["realizado_por_nombre"] == "Admin Prueba" for t in items)
    assert {t["detalle"]["placa"] is None for t in items} == {True, False}  # hay de usuarios y de vehiculos
