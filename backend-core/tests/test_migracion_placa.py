"""Migracion 0004_placa_en_accesos: baja y vuelve a subir con accesos ya existentes. Solo corre
contra la base de pruebas (la prepara conftest)."""

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
from app.models.enums import TipoVehiculo  # noqa: E402
from app.models.vehiculo import Vehiculo  # noqa: E402
from tests.conftest import RAIZ  # noqa: E402

LLAVES = {
    "accesos_vehiculo_id_fkey",
    "accesos_usuario_id_fkey",
    "accesos_autorizado_por_id_fkey",
    "auditoria_accesos_realizado_por_id_fkey",
}


def _configuracion():
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ / "alembic"))
    return configuracion


def _llaves_foraneas():
    """Nombre -> si esta validada, de las llaves foraneas de accesos y auditoria_accesos."""
    with engine.connect() as conexion:
        filas = conexion.execute(
            text(
                "SELECT conname, convalidated FROM pg_constraint WHERE contype = 'f' "
                "AND conrelid IN ('accesos'::regclass, 'auditoria_accesos'::regclass)"
            )
        ).all()
    return {nombre: validada for nombre, validada in filas}


def _columnas_de_accesos():
    with engine.connect() as conexion:
        return set(
            conexion.execute(
                text("SELECT column_name FROM information_schema.columns WHERE table_name = 'accesos'")
            ).scalars()
        )


def test_baja_y_vuelve_a_subir_rellenando_la_placa_de_los_accesos_existentes():
    ahora = datetime.now(timezone.utc)
    placa = "MIG" + str(uuid.uuid4().int)[:3]
    with SessionLocal() as db:
        # Otros tests dejan accesos de vehiculos que no estan en esta base: sin vehiculo no hay
        # de donde rellenar la placa al volver a subir.
        db.execute(text("DELETE FROM accesos WHERE vehiculo_id NOT IN (SELECT id FROM vehiculos)"))
        vehiculo = Vehiculo(placa=placa, tipo_vehiculo=TipoVehiculo.CARRO, es_visitante=True)
        db.add(vehiculo)
        db.flush()
        cerrado = Acceso(
            vehiculo_id=vehiculo.id,
            placa=placa,
            zona_id=uuid.uuid4(),
            fecha_hora_entrada=ahora - timedelta(hours=2),
            fecha_hora_salida=ahora - timedelta(hours=1),
        )
        abierto = Acceso(vehiculo_id=vehiculo.id, placa=placa, zona_id=uuid.uuid4())
        db.add_all([cerrado, abierto])
        db.commit()
        ids = [cerrado.id, abierto.id]
    engine.dispose()

    configuracion = _configuracion()
    try:
        command.downgrade(configuracion, "0003_separar_parqueadero")
        assert "placa" not in _columnas_de_accesos()
        # las llaves vuelven sin validar, para no bloquear con los datos ya registrados
        assert _llaves_foraneas() == {nombre: False for nombre in LLAVES}
        with engine.connect() as conexion:
            assert conexion.execute(text("SELECT count(*) FROM accesos WHERE id = ANY(:ids)"), {"ids": ids}).scalar() == 2

        command.upgrade(configuracion, "0004_placa_en_accesos")
        assert _llaves_foraneas() == {}
        with engine.connect() as conexion:
            placas = conexion.execute(text("SELECT placa FROM accesos WHERE id = ANY(:ids)"), {"ids": ids}).scalars().all()
            assert placas == [placa, placa]
            assert conexion.execute(
                text("SELECT is_nullable FROM information_schema.columns WHERE table_name = 'accesos' AND column_name = 'placa'")
            ).scalar() == "NO"
            assert conexion.execute(
                text("SELECT count(*) FROM pg_indexes WHERE indexname = 'uq_accesos_vehiculo_activo'")
            ).scalar() == 1
            assert conexion.execute(
                text("SELECT count(*) FROM pg_constraint WHERE conname = 'ck_accesos_placa_mayusculas'")
            ).scalar() == 1
    finally:
        engine.dispose()
        command.upgrade(configuracion, "head")
