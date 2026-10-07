"""Accesos y auditoria, con dobles de los servicios de parqueadero e identidad. Requiere
DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.identidad_client import client as identidad_client  # noqa: E402
from app.main import app  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
from app.models.enums import TipoAcceso  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402
from app.services import acceso_service, auditoria_service  # noqa: E402

API = settings.API_V1_PREFIX


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


@pytest.fixture(autouse=True)
def identidad(monkeypatch):
    """Sustituye al microservicio de identidad en todos los tests: conoce los vehiculos que el
    test le registra, da por existentes a todos los usuarios salvo ``usuarios_inexistentes`` y,
    si ``caida`` es True, falla como lo haria el servicio sin responder."""

    class Doble:
        caida = False

        def __init__(self):
            self.vehiculos = {}
            self.usuarios_inexistentes = set()

        def vehiculo(self, prefijo="VIS", estado="aprobado", propietario_estado=None):
            """Registra un vehiculo; con ``propietario_estado`` tiene dueno, sin el es de visitante."""
            vehiculo = identidad_client.VehiculoIdentidad(
                id=uuid.uuid4(),
                placa=prefijo + str(uuid.uuid4().int)[:3],
                es_visitante=propietario_estado is None,
                estado_verificacion=estado,
                propietario_id=uuid.uuid4() if propietario_estado is not None else None,
                propietario_estado_verificacion=propietario_estado,
            )
            self.vehiculos[vehiculo.id] = vehiculo
            return {"id": str(vehiculo.id), "placa": vehiculo.placa}

        def cambiar(self, vehiculo_id, **campos):
            actual = self.vehiculos[uuid.UUID(vehiculo_id)]
            self.vehiculos[actual.id] = identidad_client.VehiculoIdentidad(**{**actual.__dict__, **campos})

        def obtener_vehiculo(self, vehiculo_id):
            self._responder()
            if vehiculo_id not in self.vehiculos:
                raise identidad_client.VehiculoNoEncontradoError("El vehiculo no existe")
            return self.vehiculos[vehiculo_id]

        def usuarios_existentes(self, usuario_ids):
            self._responder()
            return set(usuario_ids) - self.usuarios_inexistentes

        def _responder(self):
            if self.caida:
                raise identidad_client.IdentidadNoDisponibleError("El servicio de identidad no esta disponible")

    doble = Doble()
    monkeypatch.setattr(identidad_client, "obtener_vehiculo", doble.obtener_vehiculo)
    monkeypatch.setattr(identidad_client, "usuarios_existentes", doble.usuarios_existentes)
    return doble


@pytest.fixture
def admin():
    return _token(rol="admin")


def _token(rol="vigilante", sub=None, minutos=5):
    """Cabeceras con un token firmado por este servicio, sin usuario en la base local."""
    payload = {"sub": sub or str(uuid.uuid4()), "exp": datetime.now(timezone.utc) + timedelta(minutes=minutos)}
    if rol is not None:
        payload["rol"] = rol
    return {"Authorization": f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')}"}


def _id_del_token(headers):
    return jwt.get_unverified_claims(headers["Authorization"].split()[1])["sub"]


def test_entrada_normal_exige_vehiculo_y_propietario_aprobados(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo("QWE", estado="pendiente", propietario_estado="pendiente")
    entrada = {"vehiculo_id": vehiculo["id"], "zona_id": str(uuid.uuid4()), "tipo_acceso": "normal"}

    r = client.post(f"{API}/accesos/entrada", headers=admin, json=entrada)
    assert r.status_code == 409 and "verificados" in r.json()["detail"]

    identidad.cambiar(vehiculo["id"], estado_verificacion="aprobado")
    assert client.post(f"{API}/accesos/entrada", headers=admin, json=entrada).status_code == 409  # dueno pendiente

    identidad.cambiar(vehiculo["id"], estado_verificacion="rechazado", propietario_estado_verificacion="aprobado")
    assert client.post(f"{API}/accesos/entrada", headers=admin, json=entrada).status_code == 409  # vehiculo rechazado

    identidad.cambiar(vehiculo["id"], estado_verificacion="aprobado")
    r = client.post(f"{API}/accesos/entrada", headers=admin, json=entrada)
    assert r.status_code == 201, r.text
    assert parqueadero.movimientos == ["ocupar"]  # los rechazos previos no tocaron cupos
    with SessionLocal() as db:
        assert db.get(Acceso, uuid.UUID(r.json()["id"])).placa == vehiculo["placa"]  # la que dio identidad


def test_entrada_normal_de_vehiculo_aprobado_sin_propietario(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()
    entrada = {"vehiculo_id": vehiculo["id"], "zona_id": str(uuid.uuid4())}
    assert client.post(f"{API}/accesos/entrada", headers=admin, json=entrada).status_code == 201


def _entrada_visitante(client, admin, vehiculo_id):
    yo = _id_del_token(admin)
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


def test_entrada_y_salida_mueven_el_cupo_en_parqueadero(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()

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


def test_sin_cupos_no_crea_el_acceso(client, admin, parqueadero, identidad):
    parqueadero.sin_cupos = True
    vehiculo = identidad.vehiculo()

    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 409
    with SessionLocal() as db:
        assert db.query(Acceso).filter(Acceso.vehiculo_id == uuid.UUID(vehiculo["id"])).count() == 0


def test_si_falla_crear_el_acceso_se_libera_el_cupo(client, admin, parqueadero, monkeypatch, identidad):
    """Compensacion: el cupo ya se ocupo en el otro servicio, pero el acceso no se puede crear
    (aqui falla su traza de auditoria)."""

    def auditoria_caida(*args, **kwargs):
        raise RuntimeError("auditoria caida")

    vehiculo = identidad.vehiculo()
    monkeypatch.setattr(auditoria_service, "registrar_auditoria", auditoria_caida)

    sin_excepciones = TestClient(app, raise_server_exceptions=False)
    assert _entrada_visitante(sin_excepciones, admin, vehiculo["id"]).status_code == 500
    assert parqueadero.movimientos == ["ocupar", "liberar"]
    assert _accesos_abiertos(vehiculo["id"]) == 0


def test_entrada_de_vehiculo_que_ya_esta_adentro_responde_409(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()
    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 201

    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 409, r.text
    assert r.json()["detail"] == "El vehiculo ya tiene un acceso activo"
    assert parqueadero.movimientos == ["ocupar"]  # el rechazo no toco el cupo
    assert _accesos_abiertos(vehiculo["id"]) == 1


def test_entradas_simultaneas_del_mismo_vehiculo_responden_409(client, admin, parqueadero, monkeypatch, identidad):
    """Carrera: las dos entradas pasan la comprobacion previa; el indice unico de acceso activo
    rechaza la segunda y se libera el cupo que ya habia ocupado."""
    vehiculo = identidad.vehiculo()
    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 201

    monkeypatch.setattr(acceso_service, "_tiene_acceso_activo", lambda db, vehiculo_id: False)
    assert _entrada_visitante(client, admin, vehiculo["id"]).status_code == 409
    assert parqueadero.movimientos == ["ocupar", "ocupar", "liberar"]
    assert _accesos_abiertos(vehiculo["id"]) == 1


def test_entrada_con_vehiculo_inexistente_responde_404(client, admin, parqueadero):
    vehiculo_id = str(uuid.uuid4())

    normal = client.post(
        f"{API}/accesos/entrada", headers=admin, json={"vehiculo_id": vehiculo_id, "zona_id": str(uuid.uuid4())}
    )
    assert normal.status_code == 404, normal.text
    assert normal.json()["detail"] == "El vehiculo no existe"

    visitante = _entrada_visitante(client, admin, vehiculo_id)
    assert visitante.status_code == 404, visitante.text

    assert parqueadero.movimientos == []  # el rechazo no toco el cupo
    assert _accesos_abiertos(vehiculo_id) == 0


def test_entrada_con_conductor_o_autorizador_inexistente_responde_404(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()
    fantasma = uuid.uuid4()
    identidad.usuarios_inexistentes.add(fantasma)
    visitante = {
        "vehiculo_id": vehiculo["id"],
        "zona_id": str(uuid.uuid4()),
        "tipo_acceso": "visitante",
        "autorizado_por_id": _id_del_token(admin),
        "justificacion": "Visita a decanatura",
    }

    r = client.post(f"{API}/accesos/entrada", headers=admin, json={**visitante, "usuario_id": str(fantasma)})
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "El conductor (usuario_id) no existe"

    r = client.post(f"{API}/accesos/entrada", headers=admin, json={**visitante, "autorizado_por_id": str(fantasma)})
    assert r.status_code == 404, r.text
    assert r.json()["detail"] == "Quien autoriza (autorizado_por_id) no existe"

    assert parqueadero.movimientos == []  # el rechazo no toco el cupo
    assert _accesos_abiertos(vehiculo["id"]) == 0

    # con usuarios que existen, la misma entrada pasa
    r = client.post(f"{API}/accesos/entrada", headers=admin, json={**visitante, "usuario_id": str(uuid.uuid4())})
    assert r.status_code == 201, r.text


def test_identidad_caida_rechaza_toda_entrada_con_503(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()
    identidad.caida = True

    normal = client.post(
        f"{API}/accesos/entrada", headers=admin, json={"vehiculo_id": vehiculo["id"], "zona_id": str(uuid.uuid4())}
    )
    assert normal.status_code == 503, normal.text
    assert normal.json()["detail"] == "El servicio de identidad no esta disponible"

    visitante = _entrada_visitante(client, admin, vehiculo["id"])
    assert visitante.status_code == 503, visitante.text

    assert parqueadero.movimientos == []  # no se toco el cupo
    assert _accesos_abiertos(vehiculo["id"]) == 0


def test_con_identidad_caida_la_lista_la_busqueda_y_la_salida_funcionan(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text
    acceso_id = r.json()["id"]

    identidad.caida = True

    activos = client.get(f"{API}/accesos", headers=admin).json()
    assert [a["placa"] for a in activos if a["id"] == acceso_id] == [vehiculo["placa"]]
    r = client.get(f"{API}/accesos/buscar", headers=admin, params={"placa": vehiculo["placa"]})
    assert r.status_code == 200 and r.json()["id"] == acceso_id
    assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin).status_code == 200
    assert parqueadero.movimientos == ["ocupar", "liberar"]


def test_accesos_y_auditoria_autorizan_solo_con_el_token(client, parqueadero):
    for ruta in (f"{API}/accesos", f"{API}/auditoria"):
        assert client.get(ruta).status_code == 401
        assert client.get(ruta, headers={"Authorization": "Bearer no-es-un-token"}).status_code == 401
        assert client.get(ruta, headers=_token(rol=None)).status_code == 401  # sin rol
        assert client.get(ruta, headers=_token(rol="jefe")).status_code == 401  # rol desconocido
        assert client.get(ruta, headers=_token(rol="admin", sub="no-es-un-uuid")).status_code == 401
        assert client.get(ruta, headers=_token(rol="admin", minutos=-5)).status_code == 401  # vencido
        assert client.get(ruta, headers=_token(rol="estudiante")).status_code == 403

    # un token valido basta: su usuario no esta en la tabla local de usuarios
    assert client.get(f"{API}/accesos", headers=_token(rol="vigilante")).status_code == 200
    assert client.get(f"{API}/auditoria", headers=_token(rol="vigilante")).status_code == 403
    assert client.get(f"{API}/auditoria", headers=_token(rol="admin")).status_code == 200


def test_un_vigilante_que_solo_existe_en_el_token_registra_entrada_y_salida(client, parqueadero, identidad):
    vigilante = _token(rol="vigilante")
    vehiculo = identidad.vehiculo()

    r = _entrada_visitante(client, vigilante, vehiculo["id"])
    assert r.status_code == 201, r.text
    assert client.post(f"{API}/accesos/{r.json()['id']}/salida", headers=vigilante).status_code == 200
    assert parqueadero.movimientos == ["ocupar", "liberar"]


def test_la_entrada_guarda_la_placa_y_la_lista_y_la_busqueda_la_usan(client, admin, parqueadero, identidad):
    vehiculo = identidad.vehiculo()
    r = _entrada_visitante(client, admin, vehiculo["id"])
    assert r.status_code == 201, r.text
    acceso_id = r.json()["id"]

    with SessionLocal() as db:
        assert db.get(Acceso, uuid.UUID(acceso_id)).placa == vehiculo["placa"]

    activos = client.get(f"{API}/accesos", headers=admin).json()
    assert [a["placa"] for a in activos if a["id"] == acceso_id] == [vehiculo["placa"]]

    # la busqueda normaliza la placa igual que antes
    r = client.get(f"{API}/accesos/buscar", headers=admin, params={"placa": f" {vehiculo['placa'].lower()} "})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == acceso_id
    assert client.get(f"{API}/accesos/buscar", headers=admin, params={"placa": "NOESTA1"}).status_code == 404


def test_un_acceso_sin_vehiculo_ni_usuarios_locales_se_lista_se_busca_y_sale(client, admin, parqueadero):
    """Ya no hay llaves foraneas: el vehiculo y los usuarios son de identidad y pueden no estar
    en esta base. La placa guardada basta para la lista, la busqueda y la salida."""
    placa = "HUE" + str(uuid.uuid4().int)[:3]
    with SessionLocal() as db:
        acceso = Acceso(
            vehiculo_id=uuid.uuid4(),
            placa=placa,
            usuario_id=uuid.uuid4(),
            zona_id=uuid.uuid4(),
            tipo_acceso=TipoAcceso.VISITANTE,
            autorizado_por_id=uuid.uuid4(),
            justificacion="Visita a decanatura",
        )
        db.add(acceso)
        db.commit()
        acceso_id = str(acceso.id)

    activos = client.get(f"{API}/accesos", headers=admin).json()
    assert [a["placa"] for a in activos if a["id"] == acceso_id] == [placa]

    r = client.get(f"{API}/accesos/buscar", headers=admin, params={"placa": placa})
    assert r.status_code == 200, r.text
    assert r.json()["id"] == acceso_id

    assert client.post(f"{API}/accesos/{acceso_id}/salida", headers=admin).status_code == 200
    assert parqueadero.movimientos == ["liberar"]
    assert client.get(f"{API}/accesos/buscar", headers=admin, params={"placa": placa}).status_code == 404


def test_las_restricciones_de_accesos_siguen_sin_llaves_foraneas():
    vehiculo_id = uuid.uuid4()
    placa = "IDX" + str(uuid.uuid4().int)[:3]

    def acceso(**campos):
        return Acceso(**{"vehiculo_id": vehiculo_id, "placa": placa, "zona_id": uuid.uuid4(), **campos})

    with SessionLocal() as db:
        db.add(acceso())
        db.commit()

        # un solo acceso activo por vehiculo
        db.add(acceso())
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == acceso_service.INDICE_ACCESO_ACTIVO
        db.rollback()

        # la placa se guarda en mayusculas, como en vehiculos
        db.add(acceso(vehiculo_id=uuid.uuid4(), placa=placa.lower()))
        with pytest.raises(IntegrityError) as error:
            db.commit()
        assert error.value.orig.diag.constraint_name == "ck_accesos_placa_mayusculas"
        db.rollback()


def _accesos_abiertos(vehiculo_id):
    with SessionLocal() as db:
        return (
            db.query(Acceso)
            .filter(Acceso.vehiculo_id == uuid.UUID(vehiculo_id), Acceso.fecha_hora_salida.is_(None))
            .count()
        )
