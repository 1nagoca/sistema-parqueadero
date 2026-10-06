"""Registro, inicio de sesion y usuarios. Requiere DATABASE_URL / SECRET_KEY en el entorno; la
base de pruebas la prepara conftest."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import RolUsuario  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

API = settings.API_V1_PREFIX


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sufijo():
    return uuid.uuid4().hex[:8]


def _crear_usuario(rol, sufijo, password, activo=True):
    """Crea un usuario directamente en la base y devuelve (id, correo)."""
    correo = f"{rol.value}-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        usuario = Usuario(
            nombre_completo=f"{rol.value.capitalize()} Prueba",
            correo_institucional=correo,
            documento_identidad=f"{rol.value[:2].upper()}{sufijo}",
            rol=rol,
            hashed_password=hashear_password(password),
            activo=activo,
        )
        db.add(usuario)
        db.commit()
        return str(usuario.id), correo


@pytest.fixture
def admin(client, sufijo):
    _, correo = _crear_usuario(RolUsuario.ADMIN, sufijo, "admin-password")
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


def test_login_rechaza_y_emite_token_con_sub_rol_y_exp(client, sufijo):
    usuario_id, correo = _crear_usuario(RolUsuario.VIGILANTE, sufijo, "vigilante-password")
    _, inactivo = _crear_usuario(RolUsuario.DOCENTE, sufijo, "docente-password", activo=False)

    def login(username, password):
        return client.post(f"{API}/auth/login", data={"username": username, "password": password})

    assert login(correo, "otra-password").status_code == 401
    assert login(f"nadie-{sufijo}@ufps.edu.co", "vigilante-password").status_code == 401
    assert login(inactivo, "docente-password").status_code == 403

    antes = datetime.now(timezone.utc)
    r = login(correo, "vigilante-password")
    assert r.status_code == 200, r.text
    assert r.json()["token_type"] == "bearer"

    payload = jwt.decode(r.json()["access_token"], settings.SECRET_KEY, algorithms=["HS256"])
    assert set(payload) == {"sub", "rol", "exp"}
    assert payload["sub"] == usuario_id
    assert payload["rol"] == "vigilante"
    vence = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    assert abs(vence - (antes + timedelta(hours=8))) < timedelta(minutes=1)


def test_me_devuelve_el_perfil_propio_y_exige_sesion(client, sufijo):
    assert client.get(f"{API}/usuarios/me").status_code == 401
    assert client.get(f"{API}/usuarios/me", headers={"Authorization": "Bearer no-es-un-token"}).status_code == 401

    assert _registrar(client, sufijo).status_code == 201
    estudiante = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")

    r = client.get(f"{API}/usuarios/me", headers=estudiante)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["correo_institucional"] == f"est-{sufijo}@ufps.edu.co"
    assert cuerpo["rol"] == "estudiante"
    assert "password" not in cuerpo and "hashed_password" not in cuerpo


def test_listar_y_obtener_usuarios_segun_rol(client, admin, sufijo):
    r = client.post(
        f"{API}/usuarios",
        headers=admin,
        json={
            "nombre_completo": "Vigilante Nuevo",
            "correo_institucional": f"v-{sufijo}@ufps.edu.co",
            "documento_identidad": f"V{sufijo}",
            "rol": "vigilante",
            "password": "una-clave-larga",
        },
    )
    assert r.status_code == 201, r.text
    vigilante_id = r.json()["id"]
    assert "password" not in r.json() and "hashed_password" not in r.json()
    vigilante = _login(client, f"v-{sufijo}@ufps.edu.co", "una-clave-larga")

    assert _registrar(client, sufijo).status_code == 201
    estudiante = _login(client, f"est-{sufijo}@ufps.edu.co", "clave-segura-1")

    # listar: solo el administrador
    assert client.get(f"{API}/usuarios").status_code == 401
    assert client.get(f"{API}/usuarios", headers=vigilante).status_code == 403
    assert client.get(f"{API}/usuarios", headers=estudiante).status_code == 403
    r = client.get(f"{API}/usuarios", headers=admin)
    assert r.status_code == 200, r.text
    assert vigilante_id in [u["id"] for u in r.json()]

    # obtener por id: administrador y vigilante
    assert client.get(f"{API}/usuarios/{vigilante_id}", headers=admin).json()["rol"] == "vigilante"
    assert client.get(f"{API}/usuarios/{vigilante_id}", headers=vigilante).status_code == 200
    assert client.get(f"{API}/usuarios/{vigilante_id}", headers=estudiante).status_code == 403
    assert client.get(f"{API}/usuarios/{uuid.uuid4()}", headers=admin).status_code == 404
