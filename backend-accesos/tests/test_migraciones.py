"""Migraciones 0004_placa_en_accesos, 0005_borrar_identidad y 0006_moto_electrica: bajan y
vuelven a subir. Solo corren contra la base de pruebas (la prepara conftest).

Los modelos de usuarios y vehiculos ya no existen en este servicio, asi que lo que esas tablas
necesitan para la prueba se crea con SQL."""

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.db.session import engine  # noqa: E402
from tests.conftest import RAIZ  # noqa: E402

TABLAS_IDENTIDAD = {"usuarios", "vehiculos", "documentos"}
ENUMS_IDENTIDAD = {"usuario_rol_enum", "vehiculo_tipo_enum", "documento_tipo_enum", "verificacion_estado_enum"}
ENUMS_ACCESOS = {"acceso_tipo_enum", "auditoria_accion_enum"}
LLAVES_ACCESOS = {
    "accesos_vehiculo_id_fkey",
    "accesos_usuario_id_fkey",
    "accesos_autorizado_por_id_fkey",
    "auditoria_accesos_realizado_por_id_fkey",
}


@pytest.fixture
def configuracion():
    """Configuracion de Alembic. Al terminar, la base vuelve a la ultima migracion aunque el
    test falle a medias."""
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ / "alembic"))
    engine.dispose()
    yield configuracion
    engine.dispose()
    os.environ["IDENTIDAD_DATOS_MIGRADOS"] = "1"
    command.upgrade(configuracion, "head")


def _escalares(sql, **parametros):
    with engine.connect() as conexion:
        return conexion.execute(text(sql), parametros).scalars().all()


def _tablas():
    return set(_escalares("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))


def _enums():
    return set(_escalares("SELECT typname FROM pg_type WHERE typtype = 'e'"))


def _version():
    return _escalares("SELECT version_num FROM alembic_version")


def _llaves_de_accesos():
    """Nombre -> si esta validada, de las llaves foraneas de accesos y auditoria_accesos."""
    with engine.connect() as conexion:
        filas = conexion.execute(
            text(
                "SELECT conname, convalidated FROM pg_constraint WHERE contype = 'f' "
                "AND conrelid IN ('accesos'::regclass, 'auditoria_accesos'::regclass)"
            )
        ).all()
    return {nombre: validada for nombre, validada in filas}


def _ejecutar(sql, **parametros):
    with engine.begin() as conexion:
        conexion.execute(text(sql), parametros)


def _crear_usuario():
    sufijo = uuid.uuid4().hex[:8]
    _ejecutar(
        "INSERT INTO usuarios (nombre_completo, correo_institucional, documento_identidad, rol, hashed_password) "
        "VALUES ('Usuario Prueba', :correo, :documento, 'vigilante', 'sin-uso')",
        correo=f"mig-{sufijo}@ufps.edu.co",
        documento=f"M{sufijo}",
    )


def test_0005_borra_las_tablas_de_identidad_y_se_niega_si_tienen_datos(configuracion, monkeypatch):
    accesos_antes = _escalares("SELECT count(*) FROM accesos")
    assert not TABLAS_IDENTIDAD & _tablas() and not ENUMS_IDENTIDAD & _enums()  # punto de partida: 0005

    # el downgrade recrea la estructura, vacia
    command.downgrade(configuracion, "0004_placa_en_accesos")
    assert TABLAS_IDENTIDAD <= _tablas() and ENUMS_IDENTIDAD <= _enums()
    assert _escalares("SELECT (SELECT count(*) FROM usuarios) + (SELECT count(*) FROM vehiculos) + (SELECT count(*) FROM documentos)") == [0]
    assert set(_escalares("SELECT indexname FROM pg_indexes WHERE tablename IN ('vehiculos', 'documentos')")) >= {
        "idx_vehiculos_usuario_id",
        "idx_documentos_usuario_id",
        "idx_documentos_vehiculo_id",
    }

    # con datos y sin confirmar, se niega y no borra nada
    _crear_usuario()
    monkeypatch.delenv("IDENTIDAD_DATOS_MIGRADOS")
    with pytest.raises(RuntimeError, match="IDENTIDAD_DATOS_MIGRADOS=1"):
        command.upgrade(configuracion, "0005_borrar_identidad")
    engine.dispose()
    assert _version() == ["0004_placa_en_accesos"]
    assert TABLAS_IDENTIDAD <= _tablas() and ENUMS_IDENTIDAD <= _enums()
    assert _escalares("SELECT count(*) FROM usuarios") == [1]

    # con las tablas vacias no hace falta confirmar
    _ejecutar("DELETE FROM usuarios")
    engine.dispose()
    command.upgrade(configuracion, "0005_borrar_identidad")
    assert not TABLAS_IDENTIDAD & _tablas()

    # con datos y confirmando, las borra
    engine.dispose()
    command.downgrade(configuracion, "0004_placa_en_accesos")
    _crear_usuario()
    engine.dispose()
    monkeypatch.setenv("IDENTIDAD_DATOS_MIGRADOS", "1")
    command.upgrade(configuracion, "0005_borrar_identidad")

    assert _version() == ["0005_borrar_identidad"]
    assert not TABLAS_IDENTIDAD & _tablas() and not ENUMS_IDENTIDAD & _enums()
    # lo de accesos no se toca
    assert {"accesos", "auditoria_accesos"} <= _tablas() and ENUMS_ACCESOS <= _enums()
    assert _escalares("SELECT count(*) FROM accesos") == accesos_antes


def test_0004_baja_y_vuelve_a_subir_rellenando_la_placa_de_los_accesos_existentes(configuracion):
    ahora = datetime.now(timezone.utc)
    placa = "MIG" + str(uuid.uuid4().int)[:3]
    vehiculo_id = uuid.uuid4()

    # 0004 rellena la placa desde vehiculos: hay que volver a tener esa tabla
    command.downgrade(configuracion, "0004_placa_en_accesos")
    _ejecutar(
        "INSERT INTO vehiculos (id, placa, tipo_vehiculo, es_visitante) VALUES (:id, :placa, 'carro', true)",
        id=vehiculo_id,
        placa=placa,
    )
    # Los accesos de otros tests son de vehiculos que no estan en esta base: sin vehiculo no
    # hay de donde rellenar la placa al volver a subir.
    _ejecutar("DELETE FROM accesos WHERE vehiculo_id NOT IN (SELECT id FROM vehiculos)")
    # Con SQL: el modelo Acceso ya trae columnas (0006) que en la 0004 no existen.
    ids = [uuid.uuid4(), uuid.uuid4()]
    _ejecutar(
        "INSERT INTO accesos (id, vehiculo_id, placa, zona_id, fecha_hora_entrada, fecha_hora_salida) VALUES "
        "(:cerrado, :vehiculo, :placa, :zona_cerrado, :entrada, :salida), "
        "(:abierto, :vehiculo, :placa, :zona_abierto, now(), NULL)",
        cerrado=ids[0],
        abierto=ids[1],
        vehiculo=vehiculo_id,
        placa=placa,
        zona_cerrado=uuid.uuid4(),
        zona_abierto=uuid.uuid4(),
        entrada=ahora - timedelta(hours=2),
        salida=ahora - timedelta(hours=1),
    )
    engine.dispose()

    command.downgrade(configuracion, "0003_separar_parqueadero")
    assert "placa" not in _escalares("SELECT column_name FROM information_schema.columns WHERE table_name = 'accesos'")
    # las llaves vuelven sin validar, para no bloquear con los datos ya registrados
    assert _llaves_de_accesos() == {nombre: False for nombre in LLAVES_ACCESOS}
    assert _escalares("SELECT count(*) FROM accesos WHERE id = ANY(:ids)", ids=ids) == [2]

    engine.dispose()
    command.upgrade(configuracion, "0004_placa_en_accesos")
    assert _llaves_de_accesos() == {}
    assert _escalares("SELECT placa FROM accesos WHERE id = ANY(:ids)", ids=ids) == [placa, placa]
    assert _escalares(
        "SELECT is_nullable FROM information_schema.columns WHERE table_name = 'accesos' AND column_name = 'placa'"
    ) == ["NO"]
    assert _escalares("SELECT count(*) FROM pg_indexes WHERE indexname = 'uq_accesos_vehiculo_activo'") == [1]
    assert _escalares("SELECT count(*) FROM pg_constraint WHERE conname = 'ck_accesos_placa_mayusculas'") == [1]

    # y los accesos, con su placa, sobreviven a que se borren las tablas de identidad
    engine.dispose()
    command.upgrade(configuracion, "head")
    assert _escalares("SELECT placa FROM accesos WHERE id = ANY(:ids)", ids=ids) == [placa, placa]


def _hay_restriccion(nombre):
    return _escalares("SELECT count(*) FROM pg_constraint WHERE conname = :nombre", nombre=nombre) == [1]


CHECKS_ELECTRICA = (
    "ck_accesos_placa_o_numero_serie",
    "ck_accesos_numero_serie_mayusculas",
    "ck_accesos_electrica_solo_normal",
)


def _columnas_de_accesos():
    return set(_escalares("SELECT column_name FROM information_schema.columns WHERE table_name = 'accesos'"))


def _placa_admite_null():
    return _escalares(
        "SELECT is_nullable FROM information_schema.columns WHERE table_name = 'accesos' AND column_name = 'placa'"
    ) == ["YES"]


def test_0006_baja_y_sube_y_se_detiene_si_hay_accesos_de_electricas(configuracion):
    # punto de partida: head, con la moto electrica
    assert {"es_electrica", "numero_serie"} <= _columnas_de_accesos() and _placa_admite_null()
    assert all(_hay_restriccion(nombre) for nombre in CHECKS_ELECTRICA)
    assert _escalares("SELECT count(*) FROM accesos WHERE es_electrica") == [0]
    accesos_antes = _escalares("SELECT count(*) FROM accesos")

    # el downgrade quita columnas y CHECK y devuelve la placa obligatoria, sin tocar los accesos
    command.downgrade(configuracion, "0005_borrar_identidad")
    engine.dispose()
    assert _version() == ["0005_borrar_identidad"]
    assert not {"es_electrica", "numero_serie"} & _columnas_de_accesos() and not _placa_admite_null()
    assert not any(_hay_restriccion(nombre) for nombre in CHECKS_ELECTRICA)
    assert _hay_restriccion("ck_accesos_placa_mayusculas")
    assert _escalares("SELECT count(*) FROM accesos") == accesos_antes

    engine.dispose()
    command.upgrade(configuracion, "head")
    assert _escalares("SELECT count(*) FROM accesos WHERE es_electrica") == [0]  # los de antes quedan con placa

    # con un acceso de una electrica, el downgrade se detiene y no cambia nada
    acceso_id = uuid.uuid4()
    ahora = datetime.now(timezone.utc)
    _ejecutar(
        "INSERT INTO accesos (id, vehiculo_id, placa, es_electrica, numero_serie, zona_id, "
        "fecha_hora_entrada, fecha_hora_salida) VALUES (:id, :vehiculo, NULL, true, 'EB-MIG12345', :zona, :entrada, :salida)",
        id=acceso_id,
        vehiculo=uuid.uuid4(),
        zona=uuid.uuid4(),
        entrada=ahora - timedelta(hours=1),
        salida=ahora,
    )
    engine.dispose()
    try:
        with pytest.raises(Exception, match="No se puede quitar la moto electrica de accesos"):
            command.downgrade(configuracion, "0005_borrar_identidad")
        engine.dispose()
        assert _version() == ["0006_moto_electrica"]
        assert {"es_electrica", "numero_serie"} <= _columnas_de_accesos()
    finally:
        _ejecutar("DELETE FROM accesos WHERE id = :id", id=acceso_id)
