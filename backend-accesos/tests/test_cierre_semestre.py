"""Cierre de semestre (RN-10): archiva y borra los accesos cerrados antes del semestre anterior.
Requiere DATABASE_URL en el entorno; la base de pruebas la prepara conftest. Cada test vacia
accesos y auditoria_accesos de la base _test porque el cierre mira toda la tabla."""

import gzip
import hashlib
import json
import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from sqlalchemy import text  # noqa: E402

from app.db import cierre_semestre  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.identidad_client import client as identidad_client  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
from app.models.auditoria_acceso import AuditoriaAcceso  # noqa: E402
from app.models.enums import AccionAuditoria  # noqa: E402
from app.services import auditoria_service, cierre_semestre_service  # noqa: E402

COLOMBIA = timezone(timedelta(hours=-5))
HOY = date(2026, 10, 23)  # semestre 2026-2: el corte es 2026-01-01


@pytest.fixture(autouse=True)
def tablas_vacias():
    with SessionLocal() as db:
        db.execute(text("TRUNCATE accesos, auditoria_accesos"))
        db.commit()


@pytest.fixture
def admin_id(monkeypatch):
    """Identidad conoce a este admin activo; otros ids se configuran en cada test."""
    admin = uuid.uuid4()
    usuarios = {admin: identidad_client.UsuarioIdentidad(id=admin, rol="admin", activo=True)}
    monkeypatch.setattr(identidad_client, "obtener_usuario", lambda usuario_id: usuarios.get(usuario_id))
    return admin


def _acceso(db, entrada, salida=None, trazas=0, tabla="accesos"):
    acceso = Acceso(
        vehiculo_id=uuid.uuid4(),
        placa="CIE12A",
        zona_id=uuid.uuid4(),
        espacio_id=uuid.uuid4(),
        fecha_hora_entrada=entrada,
        fecha_hora_salida=salida,
    )
    db.add(acceso)
    db.flush()
    for _ in range(trazas):
        db.add(
            AuditoriaAcceso(
                tabla_afectada=tabla,
                registro_id=acceso.id,
                accion=AccionAuditoria.CREACION,
                realizado_por_id=uuid.uuid4(),
                fecha_hora=entrada,
            )
        )
    return acceso.id


@pytest.fixture
def escenario():
    """Dos accesos que salen (con 2 y 1 trazas) y todo lo que debe quedarse."""
    h = lambda *args: datetime(*args, tzinfo=COLOMBIA)  # noqa: E731
    with SessionLocal() as db:
        ids = {
            "viejo": _acceso(db, h(2025, 3, 1, 10, 0), h(2025, 3, 1, 12, 0), trazas=2),
            "justo_antes": _acceso(db, h(2025, 12, 31, 20, 0), h(2025, 12, 31, 23, 30), trazas=1),
            "en_el_corte": _acceso(db, h(2025, 12, 31, 22, 0), h(2026, 1, 1, 0, 0), trazas=1),
            "abierto_viejo": _acceso(db, h(2025, 2, 1, 8, 0), None, trazas=1),
            "reciente": _acceso(db, h(2026, 3, 1, 8, 0), h(2026, 3, 1, 9, 0), trazas=1),
        }
        # traza de otra tabla con el mismo registro_id que un acceso que sale: se queda
        db.add(
            AuditoriaAcceso(
                tabla_afectada="zonas",
                registro_id=ids["viejo"],
                accion=AccionAuditoria.ACTUALIZACION,
                realizado_por_id=uuid.uuid4(),
                fecha_hora=h(2025, 3, 1, 10, 0),
            )
        )
        db.commit()
    return ids


def _estado():
    with SessionLocal() as db:
        accesos = {fila for (fila,) in db.execute(text("SELECT id FROM accesos"))}
        trazas = db.execute(text("SELECT tabla_afectada, registro_id FROM auditoria_accesos")).all()
    return accesos, trazas


def _cerrar(admin_id, carpeta, confirmar, hoy=HOY):
    with SessionLocal() as db:
        return cierre_semestre_service.cerrar_semestre(
            db, admin_id=admin_id, carpeta=carpeta, confirmar=confirmar, hoy=hoy
        )


@pytest.mark.parametrize(
    "hoy, corte",
    [
        (date(2026, 3, 15), date(2025, 7, 1)),
        (date(2026, 10, 23), date(2026, 1, 1)),
        (date(2026, 1, 1), date(2025, 7, 1)),
        (date(2026, 6, 30), date(2025, 7, 1)),
        (date(2026, 7, 1), date(2026, 1, 1)),
        (date(2026, 12, 31), date(2026, 1, 1)),
    ],
)
def test_corte_es_el_inicio_del_semestre_anterior(hoy, corte):
    assert cierre_semestre_service.corte_para(hoy) == corte


def test_simulacro_cuenta_y_no_borra_nada(admin_id, escenario, tmp_path):
    antes = _estado()
    resultado = _cerrar(admin_id, tmp_path, confirmar=False)
    assert (resultado.corte, resultado.accesos, resultado.trazas) == (date(2026, 1, 1), 2, 3)
    assert resultado.archivo is None and resultado.confirmado is False
    assert _estado() == antes
    assert list(tmp_path.iterdir()) == []


def test_confirmar_archiva_verifica_y_borra_solo_lo_que_toca(admin_id, escenario, tmp_path):
    resultado = _cerrar(admin_id, tmp_path, confirmar=True)
    assert (resultado.accesos, resultado.trazas, resultado.confirmado) == (2, 3, True)

    # en la base quedan el abierto, el del corte, el reciente y la traza de otra tabla
    accesos, trazas = _estado()
    assert accesos == {escenario["en_el_corte"], escenario["abierto_viejo"], escenario["reciente"]}
    assert ("zonas", escenario["viejo"]) in trazas
    assert not any(t == "accesos" and r in (escenario["viejo"], escenario["justo_antes"]) for t, r in trazas)

    # el archivo tiene exactamente esas filas, con todas las columnas, y su sha256 coincide
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [resultado.archivo.name, f"{resultado.archivo.name}.sha256"]
    )
    assert resultado.archivo.name.startswith("accesos-antes-de-2026-01-01-")
    assert oct(resultado.archivo.stat().st_mode & 0o777) == "0o600"
    with gzip.open(resultado.archivo, "rt", encoding="utf-8") as archivo:
        lineas = [json.loads(linea) for linea in archivo]
    cabecera, filas = lineas[0], lineas[1:]
    assert (cabecera["tipo"], cabecera["formato"], cabecera["corte"]) == ("cabecera", 1, "2026-01-01")
    assert (cabecera["accesos"], cabecera["trazas"]) == (2, 3)
    de_accesos = [f["fila"] for f in filas if f["tabla"] == "accesos"]
    de_trazas = [f["fila"] for f in filas if f["tabla"] == "auditoria_accesos"]
    assert {f["id"] for f in de_accesos} == {str(escenario["viejo"]), str(escenario["justo_antes"])}
    assert len(de_trazas) == 3 and {f["tabla_afectada"] for f in de_trazas} == {"accesos"}
    assert set(de_accesos[0]) == {c.name for c in Acceso.__table__.columns}
    assert set(de_trazas[0]) == {c.name for c in AuditoriaAcceso.__table__.columns}
    sha256 = hashlib.sha256(resultado.archivo.read_bytes()).hexdigest()
    assert resultado.sha256 == sha256
    assert (tmp_path / f"{resultado.archivo.name}.sha256").read_text() == f"{sha256}  {resultado.archivo.name}\n"

    # traza del borrado
    with SessionLocal() as db:
        (traza,) = db.query(AuditoriaAcceso).filter(AuditoriaAcceso.tabla_afectada == "cierre_semestre").all()
        assert traza.accion == AccionAuditoria.ELIMINACION and traza.realizado_por_id == admin_id
        assert traza.valores_nuevos == {
            "corte": "2026-01-01",
            "accesos": 2,
            "trazas": 3,
            "archivo": resultado.archivo.name,
            "sha256": sha256,
        }

    # la segunda corrida da 0, sin archivo ni traza nuevos
    otra = _cerrar(admin_id, tmp_path, confirmar=True)
    assert (otra.accesos, otra.trazas, otra.archivo) == (0, 0, None)
    assert len(list(tmp_path.iterdir())) == 2
    with SessionLocal() as db:
        assert db.query(AuditoriaAcceso).filter(AuditoriaAcceso.tabla_afectada == "cierre_semestre").count() == 1


def test_si_falla_el_archivo_no_se_borra_nada(admin_id, escenario, tmp_path, monkeypatch):
    def disco_lleno(*args, **kwargs):
        raise OSError("No queda espacio en el disco")

    monkeypatch.setattr(cierre_semestre_service, "_escribir_archivo", disco_lleno)
    antes = _estado()
    with pytest.raises(cierre_semestre_service.CierreError, match="no se borro nada"):
        _cerrar(admin_id, tmp_path, confirmar=True)
    assert _estado() == antes
    assert list(tmp_path.iterdir()) == []


def test_si_falla_el_borrado_el_archivo_queda_y_la_base_no_cambia(admin_id, escenario, tmp_path, monkeypatch):
    def auditoria_caida(*args, **kwargs):
        raise RuntimeError("auditoria caida")

    monkeypatch.setattr(auditoria_service, "registrar_auditoria", auditoria_caida)
    antes = _estado()
    with pytest.raises(cierre_semestre_service.CierreError, match="el archivo quedo guardado"):
        _cerrar(admin_id, tmp_path, confirmar=True)
    assert _estado() == antes
    assert len([p for p in tmp_path.iterdir() if p.name.endswith(".jsonl.gz")]) == 1


@pytest.mark.parametrize("caso", ["inexistente", "vigilante", "inactivo"])
def test_admin_id_invalido_no_hace_nada(escenario, tmp_path, monkeypatch, caso):
    usuario_id = uuid.uuid4()
    usuario = {
        "inexistente": None,
        "vigilante": identidad_client.UsuarioIdentidad(id=usuario_id, rol="vigilante", activo=True),
        "inactivo": identidad_client.UsuarioIdentidad(id=usuario_id, rol="admin", activo=False),
    }[caso]
    monkeypatch.setattr(identidad_client, "obtener_usuario", lambda _id: usuario)
    antes = _estado()
    for confirmar in (False, True):
        with pytest.raises(cierre_semestre_service.CierreError):
            _cerrar(usuario_id, tmp_path, confirmar=confirmar)
    assert _estado() == antes and list(tmp_path.iterdir()) == []


def test_con_identidad_caida_no_se_hace_nada(escenario, tmp_path, monkeypatch):
    def caida(_id):
        raise identidad_client.IdentidadNoDisponibleError("El servicio de identidad no esta disponible")

    monkeypatch.setattr(identidad_client, "obtener_usuario", caida)
    antes = _estado()
    with pytest.raises(cierre_semestre_service.CierreError, match="identidad no responde"):
        _cerrar(uuid.uuid4(), tmp_path, confirmar=True)
    assert _estado() == antes and list(tmp_path.iterdir()) == []


def test_el_comando_exige_admin_id_y_por_defecto_es_simulacro(admin_id, tmp_path, capsys):
    with pytest.raises(SystemExit) as salida:
        cierre_semestre.main([])
    assert salida.value.code == 2

    assert cierre_semestre.main(["--admin-id", str(admin_id), "--carpeta", str(tmp_path)]) == 0
    texto = capsys.readouterr().out
    assert "Corte: " in texto and "Simulacro: no se borro nada" in texto

    assert cierre_semestre.main(["--admin-id", str(uuid.uuid4()), "--carpeta", str(tmp_path)]) == 1
    assert "no existe en identidad" in capsys.readouterr().err


def test_obtener_usuario_lee_rol_y_activo_de_identidad(monkeypatch):
    import httpx

    buscado = uuid.uuid4()
    respuestas = iter(
        [
            httpx.Response(200, json=[{"id": str(buscado), "rol": "admin", "activo": False}]),
            httpx.Response(200, json=[]),
            httpx.Response(200, json=[{"id": str(buscado)}]),  # faltan campos
        ]
    )
    monkeypatch.setattr(identidad_client, "_pedir", lambda ruta, **kwargs: next(respuestas))

    assert identidad_client.obtener_usuario(buscado) == identidad_client.UsuarioIdentidad(
        id=buscado, rol="admin", activo=False
    )
    assert identidad_client.obtener_usuario(buscado) is None
    with pytest.raises(identidad_client.IdentidadNoDisponibleError):
        identidad_client.obtener_usuario(buscado)
