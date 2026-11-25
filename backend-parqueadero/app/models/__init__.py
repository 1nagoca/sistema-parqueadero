"""Importa todos los modelos para que Base.metadata (y Alembic autogenerate) los conozca."""

from app.models.auditoria_parqueadero import AuditoriaParqueadero
from app.models.espacio import Espacio
from app.models.mantenimiento import Mantenimiento
from app.models.zona import Zona

__all__ = ["AuditoriaParqueadero", "Espacio", "Mantenimiento", "Zona"]
