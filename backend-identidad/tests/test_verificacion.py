"""Flujo de autorregistro y verificacion de estudiantes, con su auditoria propia. Requiere
DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auditoria_identidad import AuditoriaIdentidad  # noqa: E402
from app.models.enums import RolUsuario  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"\x00" * 64

API = settings.API_V1_PREFIX


@pytest.fixture(autouse=True)
def carpeta_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sufijo():
    return uuid.uuid4().hex[:8]


def _personal(client, rol, sufijo):
    """Crea un usuario de personal directamente en la base y devuelve (id, cabeceras)."""
    correo = f"{rol.value}-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        usuario = Usuario(
            nombre_completo=f"{rol.value.capitalize()} Prueba",
            correo_institucional=correo,
            documento_identidad=f"{rol.value[:2].upper()}{sufijo}",
            rol=rol,
            hashed_password=hashear_password("una-password"),
        )
        db.add(usuario)
        db.commit()
        usuario_id = str(usuario.id)
    return usuario_id, _login(client, correo, "una-password")


@pytest.fixture
def admin(client, sufijo):
    return _personal(client, RolUsuario.ADMIN, sufijo)[1]


def _login(client, correo, password):
    r = client.post(f"{API}/auth/login", data={"username": correo, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _registrar(client, sufijo, **extra):
    datos = {
        "nombre_completo": "Estudiante Prueba",
        "correo_institucional": f"est-{sufijo}@ufps.edu.co",
        "documento_identidad": f"D{sufijo}",
        "password": "clave-segura-1",
        "acepta_tratamiento_datos": True,
    }
    datos.update(extra)
    return client.post(f"{API}/auth/registro", json=datos)


def _archivos(placa=PNG, tarjeta=PDF):
    return {
        "foto_placa": ("placa.png", placa, "image/png"),
        "tarjeta_propiedad": ("tarjeta.pdf", tarjeta, "application/pdf"),
    }


def _vehiculo(client, headers, placa, **kw):
    return client.post(
        f"{API}/vehiculos/mis-vehiculos",
        headers=headers,
        data={"placa": placa, "tipo_vehiculo": "carro", "marca": "Mazda", "color": "Rojo"},
        files=kw.get("files") or _archivos(),
    )


def test_flujo_completo_registro_aprobacion_y_documentos_privados(client, admin, sufijo):
    assert _registrar(client, sufijo).status_code == 201
    est = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")

    # sin carnet no aparece en la bandeja ni se puede aprobar
    pendientes = client.get(f"{API}/verificaciones/pendientes", headers=admin).json()
    assert all(s["usuario"]["correo_institucional"] != f"est-{sufijo}@ufps.edu.co" for s in pendientes)
    uid = client.get(f"{API}/usuarios/me", headers=est).json()["id"]
    r = client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": True})
    assert r.status_code == 400

    # archivo que no es imagen/pdf (aunque diga ser png) se rechaza
    r = client.post(
        f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.png", b"<html>x</html>", "image/png")}
    )
    assert r.status_code == 422
    r = client.post(f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.jpg", JPG, "image/jpeg")})
    assert r.status_code == 200, r.text

    # placa con formato invalido / foto de placa en PDF
    assert _vehiculo(client, est, "12ABC").status_code == 422
    assert _vehiculo(client, est, "ZZ1234").status_code == 422
    placa = "ABC" + str(uuid.uuid4().int)[:3]
    r = _vehiculo(client, est, placa, files=_archivos(placa=PDF))
    assert r.status_code == 422
    r = _vehiculo(client, est, placa)
    assert r.status_code == 201, r.text
    vehiculo = r.json()
    assert vehiculo["estado_verificacion"] == "pendiente"
    assert {d["tipo"] for d in vehiculo["documentos"]} == {"foto_placa", "tarjeta_propiedad"}
    assert _vehiculo(client, est, placa).status_code == 409

    # el estudiante no puede usar endpoints de admin
    assert client.get(f"{API}/verificaciones/pendientes", headers=est).status_code == 403

    # bandeja del admin: ve carnet + vehiculo con documentos
    pendientes = client.get(f"{API}/verificaciones/pendientes", headers=admin).json()
    solicitud = next(s for s in pendientes if s["usuario"]["id"] == uid)
    assert [d["tipo"] for d in solicitud["usuario"]["documentos"]] == ["carnet"]
    assert solicitud["vehiculos"][0]["placa"] == placa

    # descarga de documentos: admin y dueno si; otro estudiante no
    doc_id = solicitud["usuario"]["documentos"][0]["id"]
    r = client.get(f"{API}/documentos/{doc_id}/archivo", headers=admin)
    assert r.status_code == 200 and r.content == JPG and r.headers["content-type"] == "image/jpeg"
    assert client.get(f"{API}/documentos/{doc_id}/archivo", headers=est).status_code == 200
    otro_sufijo = uuid.uuid4().hex[:8]
    _registrar(client, otro_sufijo)
    otro = _login(client, f"est-{otro_sufijo}@ufps.edu.co", "clave-segura-1")
    assert client.get(f"{API}/documentos/{doc_id}/archivo", headers=otro).status_code == 404
    assert client.get(f"{API}/documentos/{doc_id}/archivo").status_code == 401

    # rechazo exige motivo; luego se reenvia el carnet y se aprueba
    r = client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": False})
    assert r.status_code == 400
    r = client.post(
        f"{API}/verificaciones/usuarios/{uid}/resolver",
        headers=admin,
        json={"aprobar": False, "motivo": "Carnet ilegible"},
    )
    assert r.json()["estado_verificacion"] == "rechazado" and r.json()["motivo_rechazo"] == "Carnet ilegible"
    r = client.post(f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.png", PNG, "image/png")})
    assert r.json()["estado_verificacion"] == "pendiente" and r.json()["motivo_rechazo"] is None

    r = client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": True})
    assert r.json()["estado_verificacion"] == "aprobado"
    r = client.post(
        f"{API}/verificaciones/vehiculos/{vehiculo['id']}/resolver", headers=admin, json={"aprobar": True}
    )
    assert r.json()["estado_verificacion"] == "aprobado"

    # ya aprobado: no puede volver a subir carnet
    r = client.post(f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.png", PNG, "image/png")})
    assert r.status_code == 409

    mis = client.get(f"{API}/vehiculos/mis-vehiculos", headers=est).json()
    assert [v["placa"] for v in mis] == [placa]
    # y ya no esta en la bandeja
    pendientes = client.get(f"{API}/verificaciones/pendientes", headers=admin).json()
    assert all(s["usuario"]["id"] != uid for s in pendientes)


def test_vehiculo_rechazado_se_reenvia(client, admin, sufijo):
    _registrar(client, sufijo)
    est = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")
    placa = "XYZ" + str(uuid.uuid4().int)[:3]
    vehiculo = _vehiculo(client, est, placa).json()

    # no se puede reenviar si no esta rechazado
    r = client.post(f"{API}/vehiculos/mis-vehiculos/{vehiculo['id']}/reenviar", headers=est, files=_archivos())
    assert r.status_code == 409

    r = client.post(
        f"{API}/verificaciones/vehiculos/{vehiculo['id']}/resolver",
        headers=admin,
        json={"aprobar": False, "motivo": "Placa no visible"},
    )
    assert r.json()["estado_verificacion"] == "rechazado"
    r = client.post(f"{API}/vehiculos/mis-vehiculos/{vehiculo['id']}/reenviar", headers=est, files=_archivos())
    assert r.status_code == 200, r.text
    assert r.json()["estado_verificacion"] == "pendiente"
    assert len(r.json()["documentos"]) == 2


def _estudiante_con_carnet_y_vehiculo(client, sufijo):
    """Devuelve (cabeceras, id del estudiante, id de su vehiculo), ambos pendientes."""
    assert _registrar(client, sufijo).status_code == 201
    est = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")
    uid = client.get(f"{API}/usuarios/me", headers=est).json()["id"]
    r = client.post(f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.png", PNG, "image/png")})
    assert r.status_code == 200, r.text
    r = _vehiculo(client, est, "AUD" + str(uuid.uuid4().int)[:3])
    assert r.status_code == 201, r.text
    return est, uid, r.json()["id"]


def _trazas(registro_id):
    with SessionLocal() as db:
        return (
            db.query(AuditoriaIdentidad)
            .filter(AuditoriaIdentidad.registro_id == uuid.UUID(registro_id))
            .order_by(AuditoriaIdentidad.fecha_hora)
            .all()
        )


def test_verificar_escribe_en_auditoria_identidad(client, sufijo):
    admin_id, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    _, uid, vehiculo_id = _estudiante_con_carnet_y_vehiculo(client, sufijo)

    # una resolucion rechazada por falta de motivo no deja traza
    r = client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": False})
    assert r.status_code == 400
    assert _trazas(uid) == []

    r = client.post(
        f"{API}/verificaciones/usuarios/{uid}/resolver",
        headers=admin,
        json={"aprobar": False, "motivo": "Carnet ilegible"},
    )
    assert r.status_code == 200, r.text
    r = client.post(f"{API}/verificaciones/vehiculos/{vehiculo_id}/resolver", headers=admin, json={"aprobar": True})
    assert r.status_code == 200, r.text

    (del_usuario,) = _trazas(uid)
    assert del_usuario.tabla_afectada == "usuarios"
    assert del_usuario.accion.value == "actualizacion"
    assert del_usuario.valores_anteriores == {"estado_verificacion": "pendiente"}
    assert del_usuario.valores_nuevos == {"estado_verificacion": "rechazado"}
    assert str(del_usuario.realizado_por_id) == admin_id
    assert del_usuario.motivo == "Carnet ilegible"

    (del_vehiculo,) = _trazas(vehiculo_id)
    assert del_vehiculo.tabla_afectada == "vehiculos"
    assert del_vehiculo.valores_nuevos == {"estado_verificacion": "aprobado"}
    assert str(del_vehiculo.realizado_por_id) == admin_id
    assert del_vehiculo.motivo is None

    # la auditoria de accesos es de otro servicio: en esta base ni siquiera existe la tabla
    with SessionLocal() as db:
        assert db.execute(text("SELECT to_regclass('public.auditoria_accesos')")).scalar() is None


def test_auditoria_de_verificaciones_solo_la_lee_el_administrador(client, sufijo):
    _, admin = _personal(client, RolUsuario.ADMIN, sufijo)
    _, vigilante = _personal(client, RolUsuario.VIGILANTE, sufijo)
    est, uid, vehiculo_id = _estudiante_con_carnet_y_vehiculo(client, sufijo)
    client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": True})
    client.post(f"{API}/verificaciones/vehiculos/{vehiculo_id}/resolver", headers=admin, json={"aprobar": True})

    assert client.get(f"{API}/verificaciones/auditoria").status_code == 401
    assert client.get(f"{API}/verificaciones/auditoria", headers=est).status_code == 403
    assert client.get(f"{API}/verificaciones/auditoria", headers=vigilante).status_code == 403

    r = client.get(f"{API}/verificaciones/auditoria", headers=admin)
    assert r.status_code == 200, r.text
    trazas = r.json()
    assert {uid, vehiculo_id} <= {t["registro_id"] for t in trazas}
    assert set(trazas[0]) == {
        "id",
        "tabla_afectada",
        "registro_id",
        "accion",
        "valores_anteriores",
        "valores_nuevos",
        "realizado_por_id",
        "motivo",
        "fecha_hora",
        "ip_origen",
    }

    r = client.get(f"{API}/verificaciones/auditoria", headers=admin, params={"tabla_afectada": "vehiculos"})
    assert r.status_code == 200, r.text
    assert vehiculo_id in [t["registro_id"] for t in r.json()]
    assert {t["tabla_afectada"] for t in r.json()} == {"vehiculos"}
