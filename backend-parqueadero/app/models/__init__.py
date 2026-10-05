"""Importa todos los modelos para que Base.metadata (y Alembic autogenerate) los conozca."""

from app.models.espacio import Espacio
from app.models.zona import Zona

__all__ = ["Espacio", "Zona"]
