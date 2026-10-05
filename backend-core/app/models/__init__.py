"""Importa todos los modelos para que Base.metadata (y Alembic autogenerate) los conozca."""

from app.models.acceso import Acceso
from app.models.auditoria_acceso import AuditoriaAcceso
from app.models.documento import Documento
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo

__all__ = [
    "Acceso",
    "AuditoriaAcceso",
    "Documento",
    "Usuario",
    "Vehiculo",
]
