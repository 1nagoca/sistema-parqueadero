"""Importa todos los modelos para que Base.metadata (y Alembic autogenerate) los conozca."""

from app.models.acceso import Acceso
from app.models.auditoria_acceso import AuditoriaAcceso

__all__ = [
    "Acceso",
    "AuditoriaAcceso",
]
