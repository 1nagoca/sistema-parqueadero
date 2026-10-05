"""Base de datos de pruebas. Los tests nunca tocan la base de desarrollo: se redirigen a una
base aparte (por defecto, la de DATABASE_URL con el sufijo ``_test``), que se crea sola, se
migra con Alembic y se vacia al empezar cada corrida.

Para usar otra base, definir TEST_DATABASE_URL (su nombre debe terminar en ``_test``)."""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url

SUFIJO = "_test"
RAIZ = Path(__file__).resolve().parent.parent


def _url_de_pruebas() -> URL | None:
    explicita = os.environ.get("TEST_DATABASE_URL")
    if explicita:
        return make_url(explicita)
    base = os.environ.get("DATABASE_URL")
    if not base:
        return None
    url = make_url(base)
    if url.database.endswith(SUFIJO):
        return url
    return url.set(database=f"{url.database}{SUFIJO}")


URL_PRUEBAS = _url_de_pruebas()

# Debe ocurrir al importar conftest, antes de que algun test importe `app` y este lea
# DATABASE_URL (app.core.config y app.db.session la fijan al importarse).
if URL_PRUEBAS is not None:
    if not URL_PRUEBAS.database.endswith(SUFIJO):
        raise RuntimeError(
            f"La base de pruebas debe terminar en '{SUFIJO}' (recibido: {URL_PRUEBAS.database}). "
            "Se rechaza para no vaciar una base real."
        )
    os.environ["DATABASE_URL"] = URL_PRUEBAS.render_as_string(hide_password=False)


def _crear_base_si_falta(url: URL) -> None:
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conexion:
            existe = conexion.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :nombre"), {"nombre": url.database}
            ).scalar()
            if not existe:
                conexion.execute(text(f'CREATE DATABASE "{url.database}"'))
    finally:
        admin.dispose()


def _vaciar_tablas(url: URL) -> None:
    motor = create_engine(url)
    try:
        with motor.begin() as conexion:
            tablas = conexion.execute(
                text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            ).scalars().all()
            if tablas:
                lista = ", ".join(f'"{tabla}"' for tabla in tablas)
                conexion.execute(text(f"TRUNCATE {lista} RESTART IDENTITY CASCADE"))
    finally:
        motor.dispose()


@pytest.fixture(scope="session", autouse=True)
def base_de_pruebas():
    if URL_PRUEBAS is None:
        yield
        return

    from alembic import command
    from alembic.config import Config

    _crear_base_si_falta(URL_PRUEBAS)
    configuracion = Config(str(RAIZ / "alembic.ini"))
    configuracion.set_main_option("script_location", str(RAIZ / "alembic"))
    command.upgrade(configuracion, "head")
    _vaciar_tablas(URL_PRUEBAS)
    yield
