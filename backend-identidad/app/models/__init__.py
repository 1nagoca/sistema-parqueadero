"""Importa todos los modelos para que Base.metadata (y Alembic autogenerate) los conozca."""

from app.models.auditoria_identidad import AuditoriaIdentidad
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo

__all__ = [
    "AuditoriaIdentidad",
    "Documento",
    "Usuario",
    "Vehiculo",
]
