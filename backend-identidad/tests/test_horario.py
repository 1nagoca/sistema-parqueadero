"""Horario del parqueadero (RN-11): el estudiante solo inicia sesion de 05:45 a 22:00 y su token
vence al cierre; vigilante y admin entran siempre. La hora la fija ``hora_fija`` de conftest."""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import COLOMBIA, hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import RolUsuario  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

API = settings.API_V1_PREFIX
PASSWORD = "clave-del-horario"
OCHO_HORAS = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)


@pytest.fixture
def client():
    return TestClient(app)


def _crear_usuario(rol):
    """Crea un usuario activo directamente en la base y devuelve su correo."""
    sufijo = uuid.uuid4().hex[:8]
    correo = f"horario-{rol.value}-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        db.add(
            Usuario(
                nombre_completo=f"{rol.value.capitalize()} Horario",
                correo_institucional=correo,
                documento_identidad=f"H{rol.value[:2].upper()}{sufijo}",
                rol=rol,
                hashed_password=hashear_password(PASSWORD),
            )
        )
        db.commit()
    return correo


def _login(client, correo, password=PASSWORD):
    return client.post(f"{API}/auth/login", data={"username": correo, "password": password})


def _exp(respuesta):
    claims = jwt.get_unverified_claims(respuesta.json()["access_token"])
    return datetime.fromtimestamp(claims["exp"], tz=timezone.utc)


@pytest.mark.parametrize(
    ("hora", "minuto", "esperado"), [(5, 44, 403), (5, 45, 200), (21, 59, 200), (22, 0, 403)]
)
def test_estudiante_solo_inicia_sesion_en_horario(client, hora_fija, hora, minuto, esperado):
    correo = _crear_usuario(RolUsuario.ESTUDIANTE)
    hora_fija(hora, minuto)
    r = _login(client, correo)
    assert r.status_code == esperado, r.text
    if esperado == 403:
        assert r.json()["detail"] == (
            "El parqueadero esta cerrado: los estudiantes inician sesion de 05:45 a 22:00"
        )


@pytest.mark.parametrize("rol", [RolUsuario.VIGILANTE, RolUsuario.ADMIN])
def test_vigilante_y_admin_inician_sesion_a_las_23(client, hora_fija, rol):
    correo = _crear_usuario(rol)
    hora_fija(23)
    r = _login(client, correo)
    assert r.status_code == 200, r.text
    # Su token sigue durando 8 horas desde el reloj real.
    restante = _exp(r) - datetime.now(timezone.utc)
    assert OCHO_HORAS - timedelta(minutes=1) < restante <= OCHO_HORAS


@pytest.mark.parametrize(("hora", "hora_exp"), [(21, 22), (8, 16)])
def test_token_del_estudiante_vence_al_cierre_o_a_las_8_horas(client, hora_fija, hora, hora_exp):
    correo = _crear_usuario(RolUsuario.ESTUDIANTE)
    momento = hora_fija(hora)
    r = _login(client, correo)
    assert r.status_code == 200, r.text
    assert _exp(r) == momento.replace(hour=hora_exp)


def test_credenciales_malas_de_noche_dan_401(client, hora_fija):
    correo = _crear_usuario(RolUsuario.ESTUDIANTE)
    hora_fija(23)
    r = _login(client, correo, password="otra-clave-mala")
    assert r.status_code == 401, r.text


def test_token_de_estudiante_vencido_da_401(client, hora_fija):
    correo = _crear_usuario(RolUsuario.ESTUDIANTE)
    hora_fija(21, dia=date(2020, 1, 15))
    r = _login(client, correo)
    assert r.status_code == 200, r.text
    assert _exp(r) == datetime(2020, 1, 15, 22, 0, tzinfo=COLOMBIA)
    me = client.get(f"{API}/usuarios/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 401, me.text


def test_sin_restriccion_el_estudiante_entra_a_las_23(client, hora_fija, monkeypatch):
    correo = _crear_usuario(RolUsuario.ESTUDIANTE)
    monkeypatch.setattr(settings, "HORARIO_RESTRINGIDO", False)
    hora_fija(23)
    r = _login(client, correo)
    assert r.status_code == 200, r.text
    me = client.get(f"{API}/usuarios/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
    assert me.status_code == 200, me.text
