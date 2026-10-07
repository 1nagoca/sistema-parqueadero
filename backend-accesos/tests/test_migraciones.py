"""Migraciones 0004_placa_en_accesos y 0005_borrar_identidad: bajan y vuelven a subir. Solo
corren contra la base de pruebas (la prepara conftest).

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

from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.acceso import Acceso  # noqa: E402
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
    with SessionLocal() as db:
        # Los accesos de otros tests son de vehiculos que no estan en esta base: sin vehiculo no
        # hay de donde rellenar la placa al volver a subir.
        db.execute(text("DELETE FROM accesos WHERE vehiculo_id NOT IN (SELECT id FROM vehiculos)"))
        cerrado = Acceso(
            vehiculo_id=vehiculo_id,
            placa=placa,
            zona_id=uuid.uuid4(),
            fecha_hora_entrada=ahora - timedelta(hours=2),
            fecha_hora_salida=ahora - timedelta(hours=1),
        )
        abierto = Acceso(vehiculo_id=vehiculo_id, placa=placa, zona_id=uuid.uuid4())
        db.add_all([cerrado, abierto])
        db.commit()
        ids = [cerrado.id, abierto.id]
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
