"""Utilidad de arranque para desarrollo local.

En produccion el esquema se gestiona exclusivamente con Alembic (`alembic upgrade head`).
Este script solo sirve para levantar rapido un entorno de desarrollo sin migraciones.
"""

from app import models  # noqa: F401  -- registra los modelos en Base.metadata
from app.db.base import Base
from app.db.session import engine


def crear_tablas() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    crear_tablas()
