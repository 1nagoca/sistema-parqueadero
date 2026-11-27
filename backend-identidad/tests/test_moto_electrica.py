"""Moto electrica sin placa (punto 7): registro por numero de serie, aprobacion con la foto del
serial, reenvio y busqueda del vigilante por serial. Requiere DATABASE_URL / SECRET_KEY en el
entorno; la base de pruebas la prepara conftest."""

import os
import random
import string
import uuid
from pathlib import Path

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.documento import Documento  # noqa: E402
from app.models.enums import EstadoVerificacion, RolUsuario, TipoDocumento, TipoVehiculo  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.models.vehiculo import Vehiculo  # noqa: E402
from app.schemas.interno import VehiculoInterno  # noqa: E402
from app.services import vehiculo_service  # noqa: E402

API = settings.API_V1_PREFIX
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.4\n" + b"\x00" * 64
APROBADO = EstadoVerificacion.APROBADO

# Mensajes de la API que comprueban los tests.
SERIE_REPETIDA = "El número de serie ya está registrado"
ELECTRICA_SIN_PLACA = "La moto eléctrica no lleva placa: usa su número de serie y la foto del serial"
SOLO_ELECTRICA_SERIE = "Solo la moto eléctrica lleva número de serie y foto del serial"
FALTA_SERIE = "Indica el número de serie de la moto eléctrica"
FALTA_FOTO_SERIAL = "Falta la foto del número de serie"
FALTA_PLACA = "Indica la placa de la moto"
FALTA_FOTO_PLACA = "Falta la foto de la placa"
FALTAN_DOCS_ELECTRICA = "Faltan la foto del número de serie o la prueba de propiedad (factura o tarjeta)"
MAXIMO = "Ya tienes 4 motos registradas, que es el maximo"


@pytest.fixture(autouse=True)
def carpeta_uploads(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))


@pytest.fixture
def client():
    return TestClient(app)


def _usuario(rol, *, estado=APROBADO, activo=True):
    """Crea un usuario en la base y devuelve (id, correo)."""
    sufijo = uuid.uuid4().hex[:8]
    correo = f"elec-{rol.value}-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        usuario = Usuario(
            nombre_completo=f"Dueno {sufijo}",
            correo_institucional=correo,
            documento_identidad=f"EL{sufijo}",
            rol=rol,
            hashed_password=hashear_password("una-password"),
            estado_verificacion=estado,
            activo=activo,
        )
        db.add(usuario)
        db.commit()
        return usuario.id, correo


def _sesion(client, correo):
    r = client.post(f"{API}/auth/login", data={"username": correo, "password": "una-password"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _estudiante(client):
    # Estudiante pendiente con sesion; devuelve (id, cabeceras).
    uid, correo = _usuario(RolUsuario.ESTUDIANTE, estado=EstadoVerificacion.PENDIENTE)
    return uid, _sesion(client, correo)


@pytest.fixture
def vigilante(client):
    return _sesion(client, _usuario(RolUsuario.VIGILANTE)[1])


@pytest.fixture
def admin(client):
    return _sesion(client, _usuario(RolUsuario.ADMIN)[1])


def _serie(guion=True):
    # Serial al azar de 12 o 13 caracteres (sin I, O ni Q no hace falta: no llega a 17).
    cuerpo = "".join(random.choices(string.ascii_uppercase + string.digits, k=10))
    return f"EB-{cuerpo}" if guion else f"EB{cuerpo}"


def _placa():
    letras = string.ascii_uppercase
    return "".join(random.choices(letras, k=3)) + f"{random.randrange(100):02d}" + random.choice(letras)


def _archivos_electrica(**cambios):
    archivos = {
        "foto_serial": ("serial.png", PNG, "image/png"),
        "tarjeta_propiedad": ("factura.pdf", PDF, "application/pdf"),
    }
    archivos.update(cambios)
    return {k: v for k, v in archivos.items() if v is not None}


def _archivos_normal(**cambios):
    archivos = {
        "foto_placa": ("placa.png", PNG, "image/png"),
        "tarjeta_propiedad": ("tarjeta.pdf", PDF, "application/pdf"),
    }
    archivos.update(cambios)
    return {k: v for k, v in archivos.items() if v is not None}


def _electrica(client, headers, serie, *, files=None, **datos):
    return client.post(
        f"{API}/vehiculos/mis-vehiculos",
        headers=headers,
        data={"es_electrica": "true", "numero_serie": serie, "marca": "Starker", "color": "Negro", **datos},
        files=files if files is not None else _archivos_electrica(),
    )


def _normal(client, headers, *, files=None, **datos):
    return client.post(
        f"{API}/vehiculos/mis-vehiculos",
        headers=headers,
        data={"marca": "Yamaha", "color": "Rojo", **datos},
        files=files if files is not None else _archivos_normal(),
    )


def _archivos_en_disco():
    carpeta = Path(settings.UPLOAD_DIR)
    return sorted(p.name for p in carpeta.iterdir()) if carpeta.exists() else []


def _motos_de(usuario_id):
    with SessionLocal() as db:
        return db.query(Vehiculo).filter(Vehiculo.usuario_id == usuario_id).count()


def _detalle(r):
    return r.json()["detail"]


# --- Registro del estudiante ---


def test_registra_electrica_pendiente_sin_placa_con_foto_serial(client):
    uid, est = _estudiante(client)
    serie = _serie()
    r = _electrica(client, est, f"  {serie.lower()}  ")
    assert r.status_code == 201, r.text
    cuerpo = r.json()
    assert cuerpo["es_electrica"] is True
    assert cuerpo["placa"] is None
    assert cuerpo["numero_serie"] == serie
    assert cuerpo["estado_verificacion"] == "pendiente"
    assert cuerpo["usuario_id"] == str(uid) and cuerpo["es_visitante"] is False
    assert sorted(d["tipo"] for d in cuerpo["documentos"]) == ["foto_serial", "tarjeta_propiedad"]
    assert len(_archivos_en_disco()) == 2

    # el estudiante la ve en su lista
    mis = client.get(f"{API}/vehiculos/mis-vehiculos", headers=est).json()
    assert [m["numero_serie"] for m in mis] == [serie]


def test_serial_con_espacios_en_medio_se_guarda_junto(client):
    _, est = _estudiante(client)
    serie = _serie(guion=False)
    r = _electrica(client, est, f"{serie[:4]} {serie[4:]}")
    assert r.status_code == 201, r.text
    assert r.json()["numero_serie"] == serie


def test_vin_de_17_valido_se_acepta(client):
    _, est = _estudiante(client)
    vin = "1HGBH41JXMN" + "".join(random.choices("0123456789", k=6))
    r = _electrica(client, est, vin)
    assert r.status_code == 201, r.text
    assert r.json()["numero_serie"] == vin


@pytest.mark.parametrize(
    "serie",
    [
        "EB2024",  # corto (6)
        "EB2024-",  # corto (7, con guion)
        "A" * 18,  # largo (18)
        "1HGBH41JXMN10918I",  # VIN de 17 con I
        "1HGBH41JXMN10918O",  # VIN de 17 con O
        "1HGBH41JXMN10918Q",  # VIN de 17 con Q
        "EB2024_00871",  # caracter no permitido
    ],
)
def test_serial_invalido_da_422_con_el_formato(client, serie):
    _, est = _estudiante(client)
    r = _electrica(client, est, serie)
    assert r.status_code == 422, r.text
    assert _detalle(r) == _formato_invalido(serie)
    assert _archivos_en_disco() == []


# El 422 de un serial con otro formato.
def _formato_invalido(serie):
    return (
        f"El número de serie {serie} no tiene un formato válido: de 8 a 17 letras, números o guiones,"
        " con al menos 8 letras o números; si tiene 17 caracteres, sin I, O ni Q"
    )


def test_serial_necesita_8_letras_o_numeros_sin_contar_guiones(client):
    uid, est = _estudiante(client)
    for serie in ("--------", "AB------", "ABC-12-4-"):
        r = _electrica(client, est, serie)
        assert r.status_code == 422, (serie, r.text)
        assert _detalle(r) == _formato_invalido(serie)
    assert _motos_de(uid) == 0 and _archivos_en_disco() == []

    # con 8 letras o numeros y guiones en medio si vale
    serie = "ABC-1234-5"
    r = _electrica(client, est, serie)
    assert r.status_code == 201, r.text
    assert r.json()["numero_serie"] == serie


def test_electrica_con_placa_o_foto_de_placa_da_422(client):
    uid, est = _estudiante(client)
    r = _electrica(client, est, _serie(), placa=_placa())
    assert r.status_code == 422 and _detalle(r) == ELECTRICA_SIN_PLACA

    r = _electrica(client, est, _serie(), files=_archivos_electrica(foto_placa=("placa.png", PNG, "image/png")))
    assert r.status_code == 422 and _detalle(r) == ELECTRICA_SIN_PLACA
    assert _motos_de(uid) == 0 and _archivos_en_disco() == []


def test_electrica_sin_serial_o_sin_foto_serial_da_422(client):
    uid, est = _estudiante(client)
    r = _electrica(client, est, "")
    assert r.status_code == 422 and _detalle(r) == FALTA_SERIE

    r = _electrica(client, est, _serie(), files=_archivos_electrica(foto_serial=None))
    assert r.status_code == 422 and _detalle(r) == FALTA_FOTO_SERIAL
    assert _motos_de(uid) == 0 and _archivos_en_disco() == []


def test_foto_serial_en_pdf_da_422(client):
    uid, est = _estudiante(client)
    r = _electrica(client, est, _serie(), files=_archivos_electrica(foto_serial=("s.pdf", PDF, "application/pdf")))
    assert r.status_code == 422 and _detalle(r) == "Este documento debe ser una imagen (JPG, PNG o WEBP)"
    assert _motos_de(uid) == 0 and _archivos_en_disco() == []


def test_serial_repetido_da_409_con_y_sin_guion(client):
    _, est = _estudiante(client)
    serie = _serie()
    assert _electrica(client, est, serie).status_code == 201
    antes = _archivos_en_disco()

    otro_uid, otro = _estudiante(client)
    for repetido in (serie, serie.replace("-", ""), serie.lower()):
        r = _electrica(client, otro, repetido)
        assert r.status_code == 409, (repetido, r.text)
        assert _detalle(r) == SERIE_REPETIDA
    assert _motos_de(otro_uid) == 0 and _archivos_en_disco() == antes


def test_serial_repetido_a_la_vez_da_409_por_el_indice(client, monkeypatch):
    _, est = _estudiante(client)
    serie = _serie()
    assert _electrica(client, est, serie).status_code == 201
    antes = _archivos_en_disco()

    # simula que la otra peticion guardo el serial despues de la comprobacion previa
    monkeypatch.setattr(vehiculo_service, "obtener_por_serie", lambda db, s: None)
    otro_uid, otro = _estudiante(client)
    r = _electrica(client, otro, serie.replace("-", ""))
    assert r.status_code == 409, r.text
    assert _detalle(r) == SERIE_REPETIDA
    assert _motos_de(otro_uid) == 0 and _archivos_en_disco() == antes


def test_la_electrica_cuenta_para_el_maximo_de_motos(client):
    uid, est = _estudiante(client)
    assert _electrica(client, est, _serie()).status_code == 201
    for _ in range(3):
        assert _normal(client, est, placa=_placa()).status_code == 201
    r = _normal(client, est, placa=_placa())
    assert r.status_code == 409 and _detalle(r) == MAXIMO
    r = _electrica(client, est, _serie())
    assert r.status_code == 409 and _detalle(r) == MAXIMO
    assert _motos_de(uid) == 4


def test_moto_normal_exige_placa_y_foto_de_placa_y_no_lleva_serial(client):
    uid, est = _estudiante(client)
    r = _normal(client, est)
    assert r.status_code == 422 and _detalle(r) == FALTA_PLACA

    r = _normal(client, est, placa=_placa(), files=_archivos_normal(foto_placa=None))
    assert r.status_code == 422 and _detalle(r) == FALTA_FOTO_PLACA

    r = _normal(client, est, placa=_placa(), numero_serie=_serie())
    assert r.status_code == 422 and _detalle(r) == SOLO_ELECTRICA_SERIE

    r = _normal(client, est, placa=_placa(), files=_archivos_normal(foto_serial=("s.png", PNG, "image/png")))
    assert r.status_code == 422 and _detalle(r) == SOLO_ELECTRICA_SERIE
    assert _motos_de(uid) == 0 and _archivos_en_disco() == []

    # la normal de siempre sigue igual
    r = _normal(client, est, placa=_placa())
    assert r.status_code == 201, r.text
    assert r.json()["es_electrica"] is False and r.json()["numero_serie"] is None


# --- POST /vehiculos (visitantes) ---


def test_visitante_no_registra_electricas(client, vigilante):
    for extra in ({"es_electrica": True}, {"numero_serie": _serie()}):
        placa = _placa()
        r = client.post(
            f"{API}/vehiculos",
            headers=vigilante,
            json={"placa": placa, "tipo_vehiculo": "moto", "es_visitante": True, **extra},
        )
        assert r.status_code == 422, r.text
        assert r.json()["detail"][0]["msg"].endswith("la moto eléctrica la registra el estudiante desde su panel")
        with SessionLocal() as db:
            assert vehiculo_service.obtener_por_placa(db, placa) is None


# --- Aprobacion del admin ---


def _electrica_en_bd(dueno_id, *, tipos=None, estado=None):
    """Crea una electrica con documentos falsos (sin archivo) y devuelve (id, serie)."""
    if tipos is None:
        tipos = (TipoDocumento.FOTO_SERIAL, TipoDocumento.TARJETA_PROPIEDAD)
    serie = _serie()
    with SessionLocal() as db:
        vehiculo = Vehiculo(
            placa=None,
            es_electrica=True,
            numero_serie=serie,
            tipo_vehiculo=TipoVehiculo.MOTO,
            usuario_id=dueno_id,
            estado_verificacion=estado or EstadoVerificacion.PENDIENTE,
        )
        db.add(vehiculo)
        db.flush()
        for tipo in tipos:
            db.add(
                Documento(
                    usuario_id=dueno_id,
                    vehiculo_id=vehiculo.id,
                    tipo=tipo,
                    ruta_archivo=f"{uuid.uuid4().hex}.png",
                    content_type="image/png",
                    tamano_bytes=10,
                )
            )
        db.commit()
        return vehiculo.id, serie


def test_aprobar_electrica_exige_foto_serial_y_tarjeta(client, admin):
    dueno, _ = _usuario(RolUsuario.ESTUDIANTE)
    for tipos in (
        (TipoDocumento.TARJETA_PROPIEDAD,),
        (TipoDocumento("foto_serial"),),
        (TipoDocumento.FOTO_PLACA, TipoDocumento.TARJETA_PROPIEDAD),
    ):
        vehiculo_id, _ = _electrica_en_bd(dueno, tipos=tipos)
        r = client.post(f"{API}/verificaciones/vehiculos/{vehiculo_id}/resolver", headers=admin, json={"aprobar": True})
        assert r.status_code == 400, (tipos, r.text)
        assert _detalle(r) == FALTAN_DOCS_ELECTRICA

    vehiculo_id, _ = _electrica_en_bd(dueno)
    r = client.post(f"{API}/verificaciones/vehiculos/{vehiculo_id}/resolver", headers=admin, json={"aprobar": True})
    assert r.status_code == 200, r.text
    assert r.json()["estado_verificacion"] == "aprobado" and r.json()["placa"] is None


def test_admin_ve_la_electrica_pendiente_en_su_bandeja(client, admin):
    uid, est = _estudiante(client)
    serie = _serie()
    assert _electrica(client, est, serie).status_code == 201
    r = client.get(f"{API}/verificaciones/pendientes", headers=admin)
    assert r.status_code == 200, r.text
    (solicitud,) = [s for s in r.json() if s["usuario"]["id"] == str(uid)]
    (moto,) = solicitud["vehiculos"]
    assert moto["numero_serie"] == serie and moto["placa"] is None
    assert sorted(d["tipo"] for d in moto["documentos"]) == ["foto_serial", "tarjeta_propiedad"]


# --- Reenvio ---


def test_reenviar_electrica_rechazada_con_foto_serial(client, admin):
    _, est = _estudiante(client)
    vehiculo = _electrica(client, est, _serie()).json()
    r = client.post(
        f"{API}/verificaciones/vehiculos/{vehiculo['id']}/resolver",
        headers=admin,
        json={"aprobar": False, "motivo": "Serial borroso"},
    )
    assert r.json()["estado_verificacion"] == "rechazado"
    url = f"{API}/vehiculos/mis-vehiculos/{vehiculo['id']}/reenviar"

    r = client.post(url, headers=est, files=_archivos_normal())
    assert r.status_code == 422 and _detalle(r) == ELECTRICA_SIN_PLACA
    r = client.post(url, headers=est, files=_archivos_electrica(foto_serial=None))
    assert r.status_code == 422 and _detalle(r) == FALTA_FOTO_SERIAL

    r = client.post(url, headers=est, files=_archivos_electrica())
    assert r.status_code == 200, r.text
    assert r.json()["estado_verificacion"] == "pendiente" and r.json()["motivo_rechazo"] is None
    assert sorted(d["tipo"] for d in r.json()["documentos"]) == ["foto_serial", "tarjeta_propiedad"]
    # los archivos viejos se borran: quedan solo los dos nuevos
    assert len(_archivos_en_disco()) == 2


def test_reenviar_normal_rechazada_no_acepta_foto_serial(client, admin):
    _, est = _estudiante(client)
    vehiculo = _normal(client, est, placa=_placa()).json()
    client.post(
        f"{API}/verificaciones/vehiculos/{vehiculo['id']}/resolver",
        headers=admin,
        json={"aprobar": False, "motivo": "Placa no visible"},
    )
    url = f"{API}/vehiculos/mis-vehiculos/{vehiculo['id']}/reenviar"
    r = client.post(url, headers=est, files=_archivos_normal(foto_serial=("s.png", PNG, "image/png")))
    assert r.status_code == 422 and _detalle(r) == SOLO_ELECTRICA_SERIE
    r = client.post(url, headers=est, files=_archivos_normal(foto_placa=None))
    assert r.status_code == 422 and _detalle(r) == FALTA_FOTO_PLACA


# --- Busqueda por serial (admin, vigilante) ---


def _electrica_aprobada(*, dueno_estado=APROBADO, dueno_activo=True, moto_estado=APROBADO, carnet=True):
    """Electrica de un dueno con carnet en disco; devuelve (id, serie, nombre del dueno)."""
    dueno_id, _ = _usuario(RolUsuario.ESTUDIANTE, estado=dueno_estado, activo=dueno_activo)
    vehiculo_id, serie = _electrica_en_bd(dueno_id, estado=moto_estado)
    with SessionLocal() as db:
        if carnet:
            nombre = f"{uuid.uuid4().hex}.png"
            carpeta = Path(settings.UPLOAD_DIR)
            carpeta.mkdir(parents=True, exist_ok=True)
            (carpeta / nombre).write_bytes(PNG)
            db.add(
                Documento(
                    usuario_id=dueno_id, tipo=TipoDocumento.CARNET, ruta_archivo=nombre,
                    content_type="image/png", tamano_bytes=len(PNG),
                )
            )
            db.commit()
        return vehiculo_id, serie, db.get(Usuario, dueno_id).nombre_completo


def test_buscar_por_serial_con_espacios_minusculas_y_sin_guion(client, vigilante, admin):
    vehiculo_id, serie, _ = _electrica_aprobada()
    for consulta in (serie, serie.lower(), serie.replace("-", ""), f" {serie} "):
        for cabeceras in (vigilante, admin):
            r = client.get(f"{API}/vehiculos/serie/{consulta}", headers=cabeceras)
            assert r.status_code == 200, (consulta, r.text)
            assert r.json()["id"] == str(vehiculo_id) and r.json()["numero_serie"] == serie

    r = client.get(f"{API}/vehiculos/serie/{_serie()}", headers=vigilante)
    assert r.status_code == 404 and _detalle(r) == "Vehiculo no encontrado"
    # nunca por parecido: un pedazo del serial no la encuentra
    assert client.get(f"{API}/vehiculos/serie/{serie[:-1]}", headers=vigilante).status_code == 404


def test_propietario_y_carnet_por_serial(client, vigilante, admin):
    _, serie, nombre = _electrica_aprobada()
    for cabeceras in (vigilante, admin):
        r = client.get(f"{API}/vehiculos/serie/{serie.replace('-', '')}/propietario", headers=cabeceras)
        assert r.status_code == 200, r.text
        assert r.json() == {"nombre_completo": nombre, "tiene_carnet": True}

    r = client.get(f"{API}/vehiculos/serie/{serie}/carnet", headers=vigilante)
    assert r.status_code == 200, r.text
    assert r.content == PNG and r.headers["content-type"] == "image/png"
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    "caso", ["inexistente", "moto_pendiente", "moto_rechazada", "dueno_pendiente", "dueno_de_baja", "sin_carnet"]
)
def test_serial_da_el_mismo_404_generico_de_rn09(client, vigilante, caso):
    if caso == "inexistente":
        serie = _serie()
    elif caso == "moto_pendiente":
        _, serie, _ = _electrica_aprobada(moto_estado=EstadoVerificacion.PENDIENTE)
    elif caso == "moto_rechazada":
        _, serie, _ = _electrica_aprobada(moto_estado=EstadoVerificacion.RECHAZADO)
    elif caso == "dueno_pendiente":
        _, serie, _ = _electrica_aprobada(dueno_estado=EstadoVerificacion.PENDIENTE)
    elif caso == "dueno_de_baja":
        _, serie, _ = _electrica_aprobada(dueno_activo=False)
    else:
        _, serie, _ = _electrica_aprobada(carnet=False)

    rutas = ("carnet",) if caso == "sin_carnet" else ("propietario", "carnet")
    for ruta in rutas:
        r = client.get(f"{API}/vehiculos/serie/{serie}/{ruta}", headers=vigilante)
        assert r.status_code == 404, (caso, ruta)
        assert r.json() == {"detail": "Propietario no disponible"}


def test_busqueda_por_serial_solo_vigilante_y_admin(client):
    _, serie, _ = _electrica_aprobada()
    _, est = _estudiante(client)
    for ruta in ("", "/propietario", "/carnet"):
        url = f"{API}/vehiculos/serie/{serie}{ruta}"
        assert client.get(url).status_code == 401
        assert client.get(url, headers=est).status_code == 403


# --- API interna y base de datos ---


def test_interno_no_da_la_electrica_a_accesos_hasta_la_e3(client):
    dueno, _ = _usuario(RolUsuario.ESTUDIANTE)
    vehiculo_id, _ = _electrica_en_bd(dueno, estado=APROBADO)
    r = client.get(f"/interno/vehiculos/{vehiculo_id}", headers={"X-Clave-Interna": settings.CLAVE_INTERNA})
    assert r.status_code == 404 and _detalle(r) == "Vehiculo no encontrado"

    # el contrato ya admite la electrica para cuando accesos la maneje
    interno = VehiculoInterno(
        id=vehiculo_id, placa=None, es_electrica=True, numero_serie="EB12345678",
        es_visitante=False, estado_verificacion=APROBADO, propietario=None,
    )
    assert interno.placa is None and interno.es_electrica is True


@pytest.mark.parametrize(
    "campos",
    [
        {"es_electrica": True, "placa": "ABC12D", "numero_serie": "EB12345678"},  # electrica con placa
        {"es_electrica": True, "placa": None, "numero_serie": None},  # electrica sin serial
        {"es_electrica": False, "placa": None, "numero_serie": None},  # normal sin placa
        {"es_electrica": False, "placa": "ABC12D", "numero_serie": "EB12345678"},  # normal con serial
        {"es_electrica": True, "placa": None, "numero_serie": "eb12345678"},  # serial en minusculas
        {"es_electrica": True, "placa": None, "numero_serie": "EB12345678", "visitante": True},  # de visitante
    ],
)
def test_la_base_rechaza_combinaciones_invalidas(campos):
    campos = dict(campos)
    visitante = campos.pop("visitante", False)
    dueno = None if visitante else _usuario(RolUsuario.ESTUDIANTE)[0]
    if campos["placa"]:
        campos["placa"] = _placa()
    with SessionLocal() as db:
        db.add(Vehiculo(tipo_vehiculo=TipoVehiculo.MOTO, usuario_id=dueno, es_visitante=visitante, **campos))
        with pytest.raises(IntegrityError):
            db.commit()
