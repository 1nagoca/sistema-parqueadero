"""Plano de 800 puestos (punto 5): la migracion 0004 retira 200 puestos sin borrarlos (estado
retirado) y baja capacidad y cupos; un puesto retirado no se lista, no se ocupa, no entra en
mantenimiento y no vuelve con el lote. Requiere DATABASE_URL / SECRET_KEY en el entorno; la base de
pruebas la prepara conftest."""

import os
import uuid

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.session import SessionLocal, engine  # noqa: E402
from tests.conftest import RAIZ  # noqa: E402
from tests.test_cupos import API, admin, client  # noqa: E402,F401

ANTES = "0003_mantenimiento"


# Codigos de un tramo del plano: cada letra del 01 al numero dado.
def _codigos(letras: str, hasta: int) -> list[str]:
    return [f"{letra}-{numero:02d}" for letra in letras for numero in range(1, hasta + 1)]


PLANO_1000 = _codigos("ABCDEFGH", 42) + _codigos("IJKLMNOPQRSTUV", 46) + _codigos("WX", 10)
PLANO_800 = _codigos("ABCDEFGH", 33) + _codigos("IJKLMNOPQRSTUV", 37) + _codigos("WX", 9)
RETIRADOS = sorted(set(PLANO_1000) - set(PLANO_800))


@pytest.fixture
def configuracion():
    """Configuracion de Alembic. Al terminar, la base vuelve a la ultima migracion aunque el test falle a medias."""
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ / "alembic"))
    engine.dispose()
    yield configuracion
    engine.dispose()
    command.upgrade(configuracion, "head")


def _sql(sql: str, **parametros):
    with SessionLocal() as db:
        resultado = db.execute(text(sql), parametros)
        filas = resultado.all() if resultado.returns_rows else None
        db.commit()
        return filas


# Zona con esos puestos, todos libres y con capacidad y cupos iguales a su cantidad (con SQL: vale en cualquier revision).
def _zona_con(codigos: list[str]) -> str:
    zona_id = str(uuid.uuid4())
    _sql(
        "INSERT INTO zonas (id, nombre, capacidad_total, cupos_disponibles) VALUES (:id, :nombre, :n, :n)",
        id=zona_id,
        nombre=f"Zona retiro {zona_id[:8]}",
        n=len(codigos),
    )
    _sql(
        "INSERT INTO espacios (zona_id, codigo) SELECT :zona, unnest(CAST(:codigos AS text[]))",
        zona=zona_id,
        codigos=codigos,
    )
    return zona_id


def _capacidad_y_cupos(zona_id: str) -> tuple[int, int]:
    (fila,) = _sql("SELECT capacidad_total, cupos_disponibles FROM zonas WHERE id = :id", id=zona_id)
    return fila[0], fila[1]


def _estados(zona_id: str) -> dict[str, str]:
    filas = _sql("SELECT codigo, estado::text FROM espacios WHERE zona_id = :id", id=zona_id)
    return {codigo: estado for codigo, estado in filas}


def _version() -> list[str]:
    return [fila[0] for fila in _sql("SELECT version_num FROM alembic_version")]


# Retira con SQL los puestos dados de una zona y baja capacidad y cupos, como hace la migracion.
def _retirar(zona_id: str, codigos: list[str]) -> None:
    _sql(
        "UPDATE espacios SET estado = 'retirado' WHERE zona_id = :zona AND codigo = ANY(CAST(:codigos AS text[]))",
        zona=zona_id,
        codigos=codigos,
    )
    _sql(
        "UPDATE zonas SET capacidad_total = capacidad_total - :n, cupos_disponibles = cupos_disponibles - :n "
        "WHERE id = :zona",
        zona=zona_id,
        n=len(codigos),
    )


# --- Migracion 0004 ---


def test_la_0004_retira_los_200_y_el_downgrade_los_devuelve(configuracion):
    command.downgrade(configuracion, ANTES)
    engine.dispose()
    zona = _zona_con(PLANO_1000)
    otra = _zona_con(["A-01", "A-02"])  # sin ninguno de los 200: no cambia

    command.upgrade(configuracion, "head")
    engine.dispose()
    estados = _estados(zona)
    assert len(RETIRADOS) == 200
    assert sorted(c for c, e in estados.items() if e == "retirado") == RETIRADOS
    assert sum(1 for e in estados.values() if e == "libre") == 800
    assert _capacidad_y_cupos(zona) == (800, 800)
    assert _capacidad_y_cupos(otra) == (2, 2) and set(_estados(otra).values()) == {"libre"}

    command.downgrade(configuracion, ANTES)
    engine.dispose()
    assert set(_estados(zona).values()) == {"libre"}
    assert _capacidad_y_cupos(zona) == (1000, 1000)
    valores = [fila[0] for fila in _sql("SELECT unnest(enum_range(NULL::espacio_estado_enum))::text")]
    assert valores == ["libre", "ocupado", "mantenimiento"]


def test_la_0004_se_detiene_con_un_puesto_ocupado_o_en_mantenimiento(configuracion):
    command.downgrade(configuracion, ANTES)
    engine.dispose()
    zona = _zona_con(PLANO_1000)
    _sql("UPDATE espacios SET estado = 'ocupado' WHERE zona_id = :z AND codigo = 'A-40'", z=zona)
    _sql("UPDATE espacios SET estado = 'mantenimiento' WHERE zona_id = :z AND codigo = 'I-45'", z=zona)
    antes = _estados(zona)
    try:
        with pytest.raises(Exception, match=r"A-40 \(ocupado\).*I-45 \(mantenimiento\)"):
            command.upgrade(configuracion, "head")
        engine.dispose()
        assert _version() == [ANTES]
        assert _estados(zona) == antes and _capacidad_y_cupos(zona) == (1000, 1000)
    finally:
        _sql("UPDATE espacios SET estado = 'libre' WHERE zona_id = :z", z=zona)


def test_la_0004_se_detiene_si_una_zona_quedaria_sin_capacidad(configuracion):
    command.downgrade(configuracion, ANTES)
    engine.dispose()
    zona = _zona_con(["W-10"])
    try:
        with pytest.raises(Exception, match="fuera de rango"):
            command.upgrade(configuracion, "head")
        engine.dispose()
        assert _version() == [ANTES]
        assert _estados(zona) == {"W-10": "libre"} and _capacidad_y_cupos(zona) == (1, 1)
    finally:
        _sql("DELETE FROM espacios WHERE zona_id = :z", z=zona)
        _sql("DELETE FROM zonas WHERE id = :z", z=zona)


# --- Un puesto retirado, ya en la ultima migracion ---


def _zona_api(client, admin, capacidad: int) -> str:
    r = client.post(
        f"{API}/zonas", headers=admin, json={"nombre": f"Zona {uuid.uuid4().hex[:8]}", "capacidad_total": capacidad}
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_el_retirado_no_se_lista_pero_su_codigo_sigue_para_el_historial(client, admin):
    zona = _zona_api(client, admin, 2)
    r = client.post(f"{API}/espacios", headers=admin, json={"zona_id": zona, "codigo": "A-40"})
    assert r.status_code == 201, r.text
    espacio_id = r.json()["id"]
    client.post(f"{API}/espacios", headers=admin, json={"zona_id": zona, "codigo": "A-01"})
    _sql("UPDATE espacios SET estado = 'retirado' WHERE id = :id", id=espacio_id)

    listados = client.get(f"{API}/espacios", headers=admin, params={"zona_id": zona}).json()
    assert [e["codigo"] for e in listados] == ["A-01"]
    r = client.get("/interno/espacios", params={"id": [espacio_id]})
    assert r.status_code == 200, r.text
    assert [(e["id"], e["codigo"]) for e in r.json()] == [(espacio_id, "A-40")]


def test_el_retirado_no_se_ocupa_ni_entra_en_mantenimiento(client, admin):
    zona = _zona_api(client, admin, 2)
    espacio_id = client.post(f"{API}/espacios", headers=admin, json={"zona_id": zona, "codigo": "I-45"}).json()["id"]
    _sql("UPDATE espacios SET estado = 'retirado' WHERE id = :id", id=espacio_id)

    r = client.post("/interno/cupos/ocupar", json={"zona_id": zona, "espacio_id": espacio_id})
    assert r.status_code == 409, r.text
    r = client.post(f"{API}/espacios/{espacio_id}/mantenimiento", headers=admin, json={"motivo": "Prueba de retiro"})
    assert r.status_code == 409, r.text
    assert "retirado" in r.json()["detail"]
    assert _estados(zona) == {"I-45": "retirado"} and _capacidad_y_cupos(zona) == (2, 2)


def test_el_lote_no_cuenta_ni_revive_los_retirados_y_el_reporte_da_800(client, admin):
    zona = _zona_api(client, admin, 1000)
    r = client.post(f"{API}/espacios/lote", headers=admin, json={"zona_id": zona, "codigos": PLANO_1000})
    assert r.json() == {"creados": 1000, "existentes": 0}
    _retirar(zona, RETIRADOS)  # como despues de la migracion
    assert _capacidad_y_cupos(zona) == (800, 800)

    # el plano nuevo, un codigo retirado suelto y el plano viejo (un frontend en cache): nada cambia
    for codigos in (PLANO_800, ["A-40"], PLANO_1000):
        r = client.post(f"{API}/espacios/lote", headers=admin, json={"zona_id": zona, "codigos": codigos})
        assert r.status_code == 200, r.text
        assert r.json()["creados"] == 0
        assert _capacidad_y_cupos(zona) == (800, 800)
    assert _estados(zona)["A-40"] == "retirado"
    assert sum(1 for e in _estados(zona).values() if e == "retirado") == 200

    reporte = next(z for z in client.get(f"{API}/reportes/ocupacion", headers=admin).json() if z["zona_id"] == zona)
    assert reporte["capacidad_total"] == 800 and reporte["cupos_disponibles"] == 800
    assert reporte["porcentaje_ocupacion"] == 0.0
