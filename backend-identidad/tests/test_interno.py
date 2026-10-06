"""API interna que usa el servicio de accesos (contrato en docs/arquitectura.md). Requiere
DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.enums import EstadoVerificacion, RolUsuario, TipoVehiculo  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.models.vehiculo import Vehiculo  # noqa: E402


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def sufijo():
    return uuid.uuid4().hex[:8]


def _usuario(sufijo, rol, **campos):
    with SessionLocal() as db:
        usuario = Usuario(
            nombre_completo="Nombre Privado",
            correo_institucional=f"{rol.value}-{sufijo}@ufps.edu.co",
            documento_identidad=f"{rol.value[:2].upper()}{sufijo}",
            rol=rol,
            hashed_password=hashear_password("una-password"),
            **campos,
        )
        db.add(usuario)
        db.commit()
        return str(usuario.id)


def _vehiculo(prefijo, **campos):
    with SessionLocal() as db:
        vehiculo = Vehiculo(placa=prefijo + str(uuid.uuid4().int)[:3], tipo_vehiculo=TipoVehiculo.CARRO, **campos)
        db.add(vehiculo)
        db.commit()
        return str(vehiculo.id), vehiculo.placa


def test_vehiculo_con_propietario_solo_expone_lo_del_contrato(client, sufijo):
    propietario_id = _usuario(sufijo, RolUsuario.ESTUDIANTE, estado_verificacion=EstadoVerificacion.PENDIENTE)
    vehiculo_id, placa = _vehiculo("INT", usuario_id=uuid.UUID(propietario_id))

    r = client.get(f"/interno/vehiculos/{vehiculo_id}")  # sin sesion: es una llamada entre servicios
    assert r.status_code == 200, r.text
    assert r.json() == {
        "id": vehiculo_id,
        "placa": placa,
        "es_visitante": False,
        "estado_verificacion": "aprobado",
        "propietario": {"id": propietario_id, "estado_verificacion": "pendiente"},
    }
    # sin nombres, correos ni documentos
    assert "Nombre Privado" not in r.text and "@ufps.edu.co" not in r.text


def test_vehiculo_de_visitante_no_tiene_propietario_y_el_inexistente_da_404(client):
    vehiculo_id, placa = _vehiculo("VIS", es_visitante=True)

    r = client.get(f"/interno/vehiculos/{vehiculo_id}")
    assert r.status_code == 200, r.text
    assert r.json() == {
        "id": vehiculo_id,
        "placa": placa,
        "es_visitante": True,
        "estado_verificacion": "aprobado",
        "propietario": None,
    }

    assert client.get(f"/interno/vehiculos/{uuid.uuid4()}").status_code == 404
    assert client.get("/interno/vehiculos/no-es-un-uuid").status_code == 422


def test_usuarios_devuelve_solo_los_que_existen_sin_datos_personales(client, sufijo):
    vigilante_id = _usuario(sufijo, RolUsuario.VIGILANTE)
    inactivo_id = _usuario(sufijo, RolUsuario.DOCENTE, activo=False)
    inexistente = str(uuid.uuid4())

    r = client.get("/interno/usuarios", params={"id": [vigilante_id, inexistente, inactivo_id, vigilante_id]})
    assert r.status_code == 200, r.text
    assert sorted(r.json(), key=lambda u: u["rol"]) == [
        {"id": inactivo_id, "rol": "docente", "activo": False},
        {"id": vigilante_id, "rol": "vigilante", "activo": True},
    ]
    assert "Nombre Privado" not in r.text and "@ufps.edu.co" not in r.text

    assert client.get("/interno/usuarios", params={"id": [inexistente]}).json() == []
    assert client.get("/interno/usuarios").json() == []
    assert client.get("/interno/usuarios", params={"id": "no-es-un-uuid"}).status_code == 422
