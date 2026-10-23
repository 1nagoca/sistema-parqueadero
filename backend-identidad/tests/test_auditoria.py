"""Consulta de la auditoria de verificaciones por rango de fechas (hora de Colombia) y paginada.
Requiere DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import os
import uuid
from datetime import date, datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.security import hashear_password  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.auditoria_identidad import AuditoriaIdentidad  # noqa: E402
from app.models.enums import AccionAuditoria, RolUsuario  # noqa: E402
from app.models.usuario import Usuario  # noqa: E402
from app.services import auditoria_service  # noqa: E402

API = settings.API_V1_PREFIX
COLOMBIA = timezone(timedelta(hours=-5))


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def tabla():
    """Cada test escribe en una tabla_afectada propia para que los totales no dependan de otros."""
    return f"prueba-{uuid.uuid4().hex[:8]}"


def _usuario(client, rol):
    """Crea un usuario en la base y devuelve (id, cabeceras con su token)."""
    sufijo = uuid.uuid4().hex[:8]
    correo = f"aud-{rol.value}-{sufijo}@ufps.edu.co"
    with SessionLocal() as db:
        usuario = Usuario(
            nombre_completo="Auditoria Prueba",
            correo_institucional=correo,
            documento_identidad=f"AU{sufijo}",
            rol=rol,
            hashed_password=hashear_password("una-password"),
        )
        db.add(usuario)
        db.commit()
        usuario_id = usuario.id
    r = client.post(f"{API}/auth/login", data={"username": correo, "password": "una-password"})
    assert r.status_code == 200, r.text
    return usuario_id, {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def admin(client):
    return _usuario(client, RolUsuario.ADMIN)


def _trazas(tabla, autor_id, *momentos):
    """Inserta una traza por momento y devuelve sus ids en el mismo orden (solo INSERT: la tabla es append-only)."""
    with SessionLocal() as db:
        filas = [
            AuditoriaIdentidad(
                tabla_afectada=tabla,
                registro_id=uuid.uuid4(),
                accion=AccionAuditoria.ACTUALIZACION,
                realizado_por_id=autor_id,
                fecha_hora=momento,
            )
            for momento in momentos
        ]
        db.add_all(filas)
        db.commit()
        return [str(f.id) for f in filas]


def _listar(client, cabeceras, **params):
    return client.get(f"{API}/verificaciones/auditoria", headers=cabeceras, params=params)


@pytest.mark.parametrize(
    "dia, nombre, inicio, fin",
    [
        (date(2026, 1, 1), "2026-1", date(2026, 1, 1), date(2026, 6, 30)),
        (date(2026, 6, 30), "2026-1", date(2026, 1, 1), date(2026, 6, 30)),
        (date(2026, 7, 1), "2026-2", date(2026, 7, 1), date(2026, 12, 31)),
        (date(2026, 12, 31), "2026-2", date(2026, 7, 1), date(2026, 12, 31)),
    ],
)
def test_semestre_de_una_fecha(dia, nombre, inicio, fin):
    assert auditoria_service.semestre_de(dia) == auditoria_service.Semestre(nombre, inicio, fin)


def test_sin_fechas_devuelve_solo_el_semestre_actual(client, admin, tabla):
    admin_id, cabeceras = admin
    semestre = auditoria_service.semestre_de(auditoria_service.hoy_en_colombia())
    antes_del_semestre = datetime.combine(semestre.inicio, datetime.min.time(), tzinfo=COLOMBIA) - timedelta(hours=1)
    ahora, vieja = _trazas(tabla, admin_id, datetime.now(timezone.utc), antes_del_semestre)

    r = _listar(client, cabeceras, tabla_afectada=tabla)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert (cuerpo["desde"], cuerpo["hasta"]) == (semestre.inicio.isoformat(), semestre.fin.isoformat())
    assert [t["id"] for t in cuerpo["items"]] == [ahora] and cuerpo["total"] == 1
    assert vieja not in [t["id"] for t in cuerpo["items"]]


def test_desde_y_hasta_son_inclusivos_en_hora_de_colombia(client, admin, tabla):
    admin_id, cabeceras = admin
    ids = _trazas(
        tabla,
        admin_id,
        datetime(2026, 2, 28, 23, 59, tzinfo=COLOMBIA),  # antes de desde: no
        datetime(2026, 3, 1, 0, 0, tzinfo=COLOMBIA),  # primer instante de desde: si
        datetime(2026, 3, 10, 23, 30, tzinfo=COLOMBIA),  # ultima media hora de hasta: si
        datetime(2026, 3, 11, 0, 0, tzinfo=COLOMBIA),  # dia siguiente a hasta: no
    )
    r = _listar(client, cabeceras, tabla_afectada=tabla, desde="2026-03-01", hasta="2026-03-10")
    assert r.status_code == 200, r.text
    assert [t["id"] for t in r.json()["items"]] == [ids[2], ids[1]]
    assert r.json()["total"] == 2


def test_rango_invalido_responde_422_con_mensaje(client, admin):
    _, cabeceras = admin
    for params, texto in (
        ({"desde": "2026-03-01"}, "dos fechas"),
        ({"hasta": "2026-03-01"}, "dos fechas"),
        ({"desde": "2026-03-10", "hasta": "2026-03-01"}, "posterior"),
        ({"desde": "2026-01-01", "hasta": "2026-07-04"}, "184 dias"),  # 185 dias
    ):
        r = _listar(client, cabeceras, **params)
        assert r.status_code == 422, params
        assert texto in r.json()["detail"], r.text
    assert _listar(client, cabeceras, desde="2026-07-01", hasta="2026-12-31").status_code == 200  # 184 dias
    assert _listar(client, cabeceras, desde="01/03/2026", hasta="2026-03-10").status_code == 422


def test_pagina_y_por_pagina_con_total_y_orden(client, admin, tabla):
    admin_id, cabeceras = admin
    base = datetime(2026, 4, 1, 12, 0, tzinfo=COLOMBIA)
    ids = _trazas(tabla, admin_id, *(base + timedelta(hours=h) for h in range(5)))
    nuevas_primero = list(reversed(ids))

    def pagina(n):
        r = _listar(
            client, cabeceras, tabla_afectada=tabla, desde="2026-04-01", hasta="2026-04-01", por_pagina=2, pagina=n
        )
        assert r.status_code == 200, r.text
        return r.json()

    primera = pagina(1)
    assert (primera["total"], primera["pagina"], primera["por_pagina"]) == (5, 1, 2)
    assert [t["id"] for t in primera["items"]] == nuevas_primero[:2]
    assert [t["id"] for t in pagina(2)["items"]] == nuevas_primero[2:4]
    assert [t["id"] for t in pagina(3)["items"]] == nuevas_primero[4:]
    vacia = pagina(4)
    assert vacia["items"] == [] and vacia["total"] == 5

    for params in ({"por_pagina": 201}, {"por_pagina": 0}, {"pagina": 0}):
        assert _listar(client, cabeceras, **params).status_code == 422, params


def test_tabla_afectada_se_combina_con_las_fechas(client, admin, tabla):
    admin_id, cabeceras = admin
    otra = f"{tabla}-otra"
    (de_la_tabla,) = _trazas(tabla, admin_id, datetime(2026, 5, 5, 9, 0, tzinfo=COLOMBIA))
    _trazas(otra, admin_id, datetime(2026, 5, 5, 9, 0, tzinfo=COLOMBIA))
    _trazas(tabla, admin_id, datetime(2026, 5, 20, 9, 0, tzinfo=COLOMBIA))  # fuera del rango

    r = _listar(client, cabeceras, tabla_afectada=tabla, desde="2026-05-01", hasta="2026-05-10")
    assert [t["id"] for t in r.json()["items"]] == [de_la_tabla]
    assert {t["tabla_afectada"] for t in r.json()["items"]} == {tabla}


def test_solo_el_administrador_consulta_la_auditoria(client):
    assert client.get(f"{API}/verificaciones/auditoria").status_code == 401
    for rol in (RolUsuario.VIGILANTE, RolUsuario.ESTUDIANTE):
        _, cabeceras = _usuario(client, rol)
        assert _listar(client, cabeceras).status_code == 403
