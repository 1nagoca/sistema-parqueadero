"""Flujo de autorregistro y verificacion de estudiantes. Requiere una base de datos con las
migraciones aplicadas (`alembic upgrade head`) y DATABASE_URL / SECRET_KEY en el entorno."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
from app.models.enums import RolUsuario  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import acceso_service, auditoria_service  # noqa: E402

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
def parqueadero(monkeypatch):
    """Sustituye al microservicio de parqueadero: anota los movimientos de cupo que le piden
    y, si ``sin_cupos`` es True, rechaza ocupar como lo haria una zona llena."""

    class Doble:
        sin_cupos = False

        def __init__(self):
            self.movimientos = []

        def ocupar_cupo(self, zona_id, espacio_id):
            if self.sin_cupos:
                raise parqueadero_client.CupoNoDisponibleError("La zona no tiene cupos disponibles")
            self.movimientos.append("ocupar")

        def liberar_cupo(self, zona_id, espacio_id):
            self.movimientos.append("liberar")

    doble = Doble()
    monkeypatch.setattr(parqueadero_client, "ocupar_cupo", doble.ocupar_cupo)
    monkeypatch.setattr(parqueadero_client, "liberar_cupo", doble.liberar_cupo)
    monkeypatch.setattr(parqueadero_client, "codigos_de_espacios", lambda ids: {})
    return doble


@pytest.fixture
def sufijo():
    return uuid.uuid4().hex[:8]


@pytest.fixture
def admin(client, sufijo):
    correo = f"admin-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        db.add(
            Usuario(
                nombre_completo="Admin Prueba",
                correo_institucional=correo,
                documento_identidad=f"A{sufijo}",
                rol=RolUsuario.ADMIN,
                hashed_password=hashear_password("admin-password"),
            )
        )
        db.commit()
    return _login(client, correo, "admin-password")


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


def test_registro_valida_dominio_consentimiento_y_duplicados(client, sufijo):
    assert _registrar(client, sufijo, correo_institucional=f"x-{sufijo}@gmail.com").status_code == 422
    assert _registrar(client, sufijo, acepta_tratamiento_datos=False).status_code == 422
    assert _registrar(client, sufijo, password="corta").status_code == 422

    r = _registrar(client, sufijo)
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["rol"] == "estudiante"
    assert cuerpo["estado_verificacion"] == "pendiente"
    assert cuerpo["universidad"] == settings.UNIVERSIDAD_NOMBRE
    assert "password" not in cuerpo and "hashed_password" not in cuerpo

    assert _registrar(client, sufijo).status_code == 409


def test_admin_no_puede_crear_estudiantes(client, admin, sufijo):
    r = client.post(
        f"{API}/usuarios",
        headers=admin,
        json={
            "nombre_completo": "Otro",
            "correo_institucional": f"o-{sufijo}@ufps.edu.co",
            "documento_identidad": f"O{sufijo}",
            "rol": "estudiante",
            "password": "una-clave-larga",
        },
    )
    assert r.status_code == 400


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


def test_entrada_normal_exige_vehiculo_y_propietario_aprobados(client, admin, sufijo, parqueadero):
    _registrar(client, sufijo)
    est = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")
    uid = client.get(f"{API}/usuarios/me", headers=est).json()["id"]
    placa = "QWE" + str(uuid.uuid4().int)[:3]
    vehiculo = _vehiculo(client, est, placa).json()
    client.post(f"{API}/usuarios/me/carnet", headers=est, files={"archivo": ("c.png", PNG, "image/png")})

    entrada = {"vehiculo_id": vehiculo["id"], "zona_id": str(uuid.uuid4()), "tipo_acceso": "normal"}

    r = client.post(f"{API}/accesos/entrada", headers=admin, json=entrada)
    assert r.status_code == 409 and "verificados" in r.json()["detail"]

    client.post(f"{API}/verificaciones/vehiculos/{vehiculo['id']}/resolver", headers=admin, json={"aprobar": True})
    assert client.post(f"{API}/accesos/entrada", headers=admin, json=entrada).status_code == 409  # dueno pendiente

    client.post(f"{API}/verificaciones/usuarios/{uid}/resolver", headers=admin, json={"aprobar": True})
    assert client.post(f"{API}/accesos/entrada", headers=admin, json=entrada).status_code == 201
    assert parqueadero.movimientos == ["ocupar"]  # los rechazos previos no tocaron cupos


def _vehiculo_visitante(client, admin):
    placa = "VIS" + str(uuid.uuid4().int)[:3]
    r = client.post(
        f"{API}/vehiculos", headers=admin, json={"placa": placa, "tipo_vehiculo": "carro", "es_visitante": True}
    )
    assert r.status_code == 201, r.text
    return r.json()


def _entrada_visitante(client, admin, vehiculo_id):
    yo = client.get(f"{API}/usuarios/me", headers=admin).json()["id"]
    return client.post(
        f"{API}/accesos/entrada",
        headers=admin,
        json={
            "vehiculo_id": vehiculo_id,
            "zona_id": str(uuid.uuid4()),
            "tipo_acceso": "visitante",
            "autorizado_por_id": yo,
            "justificacion": "Visita a decanatura",
        },
    )


def test_entrada_y_salida_mueven_el_cupo_en_parqueadero(client, admin, parqueadero):
    vehiculo = _vehiculo_visitante(client, admin)

    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text
    assert parqueadero.movimientos == ["ocupar"]

    activos = client.get(f"{API}/accesos", headers=admin).json()
    assert vehiculo["placa"] in [a["placa"] for a in activos]

    acceso_id = r.json()["id"]
    assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin).status_code == 200
    assert parqueadero.movimientos == ["ocupar", "liberar"]
    # Segunda salida sobre el mismo acceso: no existe abierto y no vuelve a liberar el cupo.
    assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin).status_code == 404
    assert parqueadero.movimientos == ["ocupar", "liberar"]


def test_sin_cupos_no_crea_el_acceso(client, admin, parqueadero):
    parqueadero.sin_cupos = True
    vehiculo = _vehiculo_visitante(client, admin)

    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 409
    with SessionLocal() as db:
        assert db.query(Acceso).filter(Acceso.vehiculo_id == uuid.UUID(vehiculo["id"])).count() == 0


def test_si_falla_crear_el_acceso_se_libera_el_cupo(client, admin, parqueadero, monkeypatch):
    """Compensacion: el cupo ya se ocupo en el otro servicio, pero el acceso no se puede crear
    (aqui falla su traza de auditoria)."""

    def auditoria_caida(*args, **kwargs):
        raise RuntimeError("auditoria caida")

    vehiculo = _vehiculo_visitante(client, admin)
    monkeypatch.setattr(auditoria_service, "registrar_auditoria", auditoria_caida)

    sin_excepciones = TestClient(app, raise_server_exceptions=False)
    assert _entrada_visitante(sin_excepciones, admin, vehiculo["id"]).status_code == 500
    assert parqueadero.movimientos == ["ocupar", "liberar"]
    assert _accesos_abiertos(vehiculo["id"]) == 0


def test_entrada_de_vehiculo_que_ya_esta_adentro_responde_409(client, admin, parqueadero):
    vehiculo = _vehiculo_visitante(client, admin)
    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 201

    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "El vehiculo ya tiene un acceso activo"
    assert parqueadero.movimientos == ["ocupar"]  # el rechazo no toco el cupo
    assert _accesos_abiertos(vehiculo["id"]) == 1


def test_entradas_simultaneas_del_mismo_vehiculo_responden_409(client, admin, parqueadero, monkeypatch):
    """Carrera: las dos entradas pasan la comprobacion previa; el indice unico de acceso activo
    rechaza la segunda y se libera el cupo que ya habia ocupado."""
    vehiculo = _vehiculo_visitante(client, admin)
    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 201

    monkeypatch.setattr(acceso_service, "_tiene_acceso_activo", lambda db, vehiculo_id: False)
    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 409
    assert parqueadero.movimientos == ["ocupar", "ocupar", "liberar"]
    assert _accesos_abiertos(vehiculo["id"]) == 1


def _accesos_abiertos(vehiculo_id):
    with SessionLocal() as db:
        return (
            db.query(Acceso)
            .filter(Acceso.vehiculo_id == uuid.UUID(vehiculo_id), Acceso.fecha_hora_salida.is_(None))
            .count()
        )
