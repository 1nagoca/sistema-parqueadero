"""Siembra del administrador y el vigilante. Requiere DATABASE_URL / SECRET_KEY en el entorno;
la base de pruebas la prepara conftest. Las contrasenas se generan al azar en cada corrida."""

import os
import secrets
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db import seed  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import EstadoVerificacion, RolUsuario  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402

API = settings.API_V1_PREFIX


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def entorno():
    """Variables SEED_* validas, con correos y documentos unicos para no chocar entre tests."""
    sufijo = uuid.uuid4().hex[:8]
    return {
        "SEED_ADMIN_CORREO": f"seed-admin-{sufijo}@uni.edu.co",
        "SEED_ADMIN_PASSWORD": secrets.token_urlsafe(16),
        "SEED_ADMIN_DOCUMENTO": f"SA{sufijo}",
        "SEED_VIGILANTE_CORREO": f"seed-vigilante-{sufijo}@uni.edu.co",
        "SEED_VIGILANTE_PASSWORD": secrets.token_urlsafe(16),
        "SEED_VIGILANTE_DOCUMENTO": f"SV{sufijo}",
    }


def _sembrar(entorno):
    with SessionLocal() as db:
        return seed.sembrar_usuarios(db, seed.datos_desde_entorno(entorno))


def _usuario(correo):
    with SessionLocal() as db:
        return db.query(Usuario).filter(Usuario.correo_institucional == correo).first()


def _cuantos(entorno):
    correos = [entorno["SEED_ADMIN_CORREO"], entorno["SEED_VIGILANTE_CORREO"]]
    with SessionLocal() as db:
        return db.query(Usuario).filter(Usuario.correo_institucional.in_(correos)).count()


def _login(client, correo, password):
    return client.post(f"{API}/auth/login", data={"username": correo, "password": password})


def test_sembrar_crea_admin_y_vigilante_que_pueden_iniciar_sesion(client, entorno):
    resultados = _sembrar(entorno)
    assert resultados == [
        (entorno["SEED_ADMIN_CORREO"], RolUsuario.ADMIN, True),
        (entorno["SEED_VIGILANTE_CORREO"], RolUsuario.VIGILANTE, True),
    ]

    for prefijo, rol in (("ADMIN", RolUsuario.ADMIN), ("VIGILANTE", RolUsuario.VIGILANTE)):
        correo, password = entorno[f"SEED_{prefijo}_CORREO"], entorno[f"SEED_{prefijo}_PASSWORD"]
        usuario = _usuario(correo)
        assert usuario.rol == rol
        assert usuario.activo is True
        assert usuario.estado_verificacion == EstadoVerificacion.APROBADO
        # en la base solo queda el hash
        assert usuario.hashed_password != password and password not in usuario.hashed_password
        assert usuario.hashed_password.startswith("$2")

        r = _login(client, correo, password)
        assert r.status_code == 200, r.text
        yo = client.get(f"{API}/usuarios/me", headers={"Authorization": f"Bearer {r.json()['access_token']}"})
        assert yo.json()["rol"] == rol.value


def test_sembrar_dos_veces_no_duplica_ni_cambia_la_contrasena(client, entorno):
    _sembrar(entorno)
    original = _usuario(entorno["SEED_ADMIN_CORREO"]).hashed_password

    otra = dict(entorno, SEED_ADMIN_PASSWORD=secrets.token_urlsafe(16))
    resultados = _sembrar(otra)

    assert [creado for _, _, creado in resultados] == [False, False]
    assert _cuantos(entorno) == 2
    assert _usuario(entorno["SEED_ADMIN_CORREO"]).hashed_password == original
    assert _login(client, entorno["SEED_ADMIN_CORREO"], entorno["SEED_ADMIN_PASSWORD"]).status_code == 200
    assert _login(client, entorno["SEED_ADMIN_CORREO"], otra["SEED_ADMIN_PASSWORD"]).status_code == 401


@pytest.mark.parametrize(
    "cambio",
    [
        {"SEED_VIGILANTE_PASSWORD": ""},
        {"SEED_VIGILANTE_PASSWORD": None},  # variable sin definir
        {"SEED_VIGILANTE_PASSWORD": "x" * (seed.MIN_PASSWORD - 1)},
        {"SEED_ADMIN_PASSWORD": "x" * (seed.MAX_PASSWORD_BYTES + 1)},
        {"SEED_VIGILANTE_CORREO": ""},
        {"SEED_VIGILANTE_CORREO": "no-es-un-correo"},
    ],
    ids=["password-vacia", "password-ausente", "password-corta", "password-larga", "sin-correo", "correo-invalido"],
)
def test_datos_invalidos_fallan_sin_crear_a_nadie(entorno, cambio):
    incompleto = {k: v for k, v in {**entorno, **cambio}.items() if v is not None}

    with pytest.raises(seed.SiembraError):
        _sembrar(incompleto)

    # ni siquiera el usuario cuyos datos estaban bien
    assert _cuantos(entorno) == 0


def test_documento_ya_usado_o_correo_repetido_fallan_sin_crear_a_nadie(entorno):
    mismo_correo = dict(entorno, SEED_VIGILANTE_CORREO=entorno["SEED_ADMIN_CORREO"].upper())
    with pytest.raises(seed.SiembraError):
        _sembrar(mismo_correo)

    mismo_documento = dict(entorno, SEED_VIGILANTE_DOCUMENTO=entorno["SEED_ADMIN_DOCUMENTO"])
    with pytest.raises(seed.SiembraError):
        _sembrar(mismo_documento)

    assert _cuantos(entorno) == 0


def test_nombre_y_documento_tienen_valores_por_defecto():
    admin, vigilante = seed.datos_desde_entorno({"SEED_ADMIN_NOMBRE": "  ", "SEED_VIGILANTE_NOMBRE": "Ana Ruiz"})

    assert (admin.rol, admin.nombre_completo, admin.documento_identidad) == (
        RolUsuario.ADMIN,
        "Administrador del sistema",
        "SEED-ADMIN",
    )
    assert (vigilante.rol, vigilante.nombre_completo, vigilante.documento_identidad) == (
        RolUsuario.VIGILANTE,
        "Ana Ruiz",
        "SEED-VIGILANTE",
    )
    # no hay contrasena por defecto
    assert admin.password == "" and vigilante.password == ""


def test_el_script_no_imprime_contrasenas_ni_hashes(entorno, monkeypatch, capsys):
    for nombre in [n for n in os.environ if n.startswith("SEED_")]:
        monkeypatch.delenv(nombre)
    for nombre, valor in entorno.items():
        monkeypatch.setenv(nombre, valor)

    assert seed.main() == 0
    assert seed.main() == 0  # segunda vez: ya existen
    salida = capsys.readouterr()
    texto = salida.out + salida.err
    assert entorno["SEED_ADMIN_CORREO"] in texto and "creado" in texto and "ya existia" in texto

    corta = "y" * (seed.MIN_PASSWORD - 1)
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", corta)
    assert seed.main() == 1
    fallo = capsys.readouterr()
    assert "no se creo ningun usuario" in fallo.err
    texto += fallo.out + fallo.err

    secretos = [entorno["SEED_ADMIN_PASSWORD"], entorno["SEED_VIGILANTE_PASSWORD"], corta]
    secretos += [_usuario(entorno[f"SEED_{p}_CORREO"]).hashed_password for p in ("ADMIN", "VIGILANTE")]
    assert all(secreto not in texto for secreto in secretos)
    assert entorno["SEED_ADMIN_PASSWORD"] not in repr(seed.datos_desde_entorno(entorno))
