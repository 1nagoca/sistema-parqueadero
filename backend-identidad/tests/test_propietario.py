"""Lo que ve el vigilante del dueno de una moto al buscar su placa (RN-09). Requiere
DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import os
import random
import string
import uuid
from pathlib import Path

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.documento import Documento  # noqa: E402
from app.models.enums import EstadoVerificacion, RolUsuario, TipoDocumento, TipoVehiculo  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.models.vehiculo import Vehiculo  # noqa: E402

API = settings.API_V1_PREFIX
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"\x00" * 64
APROBADO = EstadoVerificacion.APROBADO


@pytest.fixture(autouse=True)
def carpeta_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))


@pytest.fixture
def client():
    return TestClient(app)


def _usuario(rol, *, estado=APROBADO, activo=True, password="una-password"):
    """Crea un usuario en la base y devuelve (id, correo)."""
    sufijo = uuid.uuid4().hex[:8]
    correo = f"prop-{rol.value}-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        usuario = Usuario(
            nombre_completo=f"Dueno {sufijo}",
            correo_institucional=correo,
            documento_identidad=f"PR{sufijo}",
            telefono="3001234567",
            rol=rol,
            hashed_password=hashear_password(password),
            estado_verificacion=estado,
            activo=activo,
        )
        db.add(usuario)
        db.commit()
        return usuario.id, correo


def _sesion(client, rol):
    _, correo = _usuario(rol)
    r = client.post(f"{API}/auth/login", data={"username": correo, "password": "una-password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def vigilante(client):
    return _sesion(client, RolUsuario.VIGILANTE)


@pytest.fixture
def admin(client):
    return _sesion(client, RolUsuario.ADMIN)


def _placa():
    # Placa de moto con letras y numeros al azar: con un prefijo fijo chocaban dentro de una corrida.
    letras = string.ascii_uppercase
    return "".join(random.choices(letras, k=3)) + f"{random.randrange(100):02d}" + random.choice(letras)


def _moto(*, dueno_estado=APROBADO, dueno_activo=True, moto_estado=APROBADO, carnet=PNG, en_disco=True):
    """Crea un dueno, su moto y, si se pide, su carnet en disco; devuelve (placa, nombre del dueno)."""
    dueno_id, _ = _usuario(RolUsuario.ESTUDIANTE, estado=dueno_estado, activo=dueno_activo)
    placa = _placa()
    with SessionLocal() as db:
        db.add(Vehiculo(placa=placa, tipo_vehiculo=TipoVehiculo.MOTO, usuario_id=dueno_id, estado_verificacion=moto_estado))
        if carnet is not None:
            es_pdf = carnet.startswith(b"%PDF")
            nombre = f"{uuid.uuid4().hex}{'.pdf' if es_pdf else '.png'}"
            if en_disco:
                carpeta = Path(settings.UPLOAD_DIR)
                carpeta.mkdir(parents=True, exist_ok=True)
                (carpeta / nombre).write_bytes(carnet)
            db.add(
                Documento(
                    usuario_id=dueno_id,
                    tipo=TipoDocumento.CARNET,
                    ruta_archivo=nombre,
                    content_type="application/pdf" if es_pdf else "image/png",
                    tamano_bytes=len(carnet),
                )
            )
        db.commit()
        nombre_dueno = db.get(Usuario, dueno_id).nombre_completo
    return placa, nombre_dueno


def _visitante():
    placa = _placa()
    with SessionLocal() as db:
        db.add(Vehiculo(placa=placa, tipo_vehiculo=TipoVehiculo.MOTO, es_visitante=True))
        db.commit()
    return placa


def test_vigilante_y_admin_ven_solo_nombre_y_si_hay_carnet(client, vigilante, admin):
    placa, nombre = _moto()
    for cabeceras in (vigilante, admin):
        r = client.get(f"{API}/vehiculos/placa/{placa.lower()}/propietario", headers=cabeceras)
        assert r.status_code == 200, r.text
        assert r.json() == {"nombre_completo": nombre, "tiene_carnet": True}
        # sin correo, documento, telefono ni ids
        assert "@ufps.edu.co" not in r.text and "PR" not in r.text and "3001234567" not in r.text


def test_carnet_devuelve_el_archivo_sin_cache(client, vigilante):
    for contenido, tipo in ((PNG, "image/png"), (PDF, "application/pdf")):
        placa, _ = _moto(carnet=contenido)
        r = client.get(f"{API}/vehiculos/placa/{placa}/carnet", headers=vigilante)
        assert r.status_code == 200, r.text
        assert r.content == contenido
        assert r.headers["content-type"] == tipo
        assert r.headers["cache-control"] == "private, no-store"
        assert r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "caso",
    ["inexistente", "visitante", "moto_pendiente", "moto_rechazada", "dueno_pendiente", "dueno_de_baja"],
)
def test_404_generico_cuando_no_se_puede_ver(client, vigilante, caso):
    if caso == "inexistente":
        placa = _placa()
    elif caso == "visitante":
        placa = _visitante()
    elif caso == "moto_pendiente":
        placa, _ = _moto(moto_estado=EstadoVerificacion.PENDIENTE)
    elif caso == "moto_rechazada":
        placa, _ = _moto(moto_estado=EstadoVerificacion.RECHAZADO)
    elif caso == "dueno_pendiente":
        placa, _ = _moto(dueno_estado=EstadoVerificacion.PENDIENTE)
    else:
        placa, _ = _moto(dueno_activo=False)

    for ruta in ("propietario", "carnet"):
        r = client.get(f"{API}/vehiculos/placa/{placa}/{ruta}", headers=vigilante)
        assert r.status_code == 404, (caso, ruta)
        assert r.json() == {"detail": "Propietario no disponible"}


def test_sin_carnet_o_sin_archivo_no_hay_nada_que_mostrar(client, vigilante):
    for placa, _ in (_moto(carnet=None), _moto(en_disco=False)):
        r = client.get(f"{API}/vehiculos/placa/{placa}/propietario", headers=vigilante)
        assert r.status_code == 200 and r.json()["tiene_carnet"] is False
        r = client.get(f"{API}/vehiculos/placa/{placa}/carnet", headers=vigilante)
        assert r.status_code == 404 and r.json() == {"detail": "Propietario no disponible"}


def test_solo_vigilante_y_admin(client):
    placa, _ = _moto()
    estudiante = _sesion(client, RolUsuario.ESTUDIANTE)
    for ruta in ("propietario", "carnet"):
        url = f"{API}/vehiculos/placa/{placa}/{ruta}"
        assert client.get(url).status_code == 401
        assert client.get(url, headers=estudiante).status_code == 403
