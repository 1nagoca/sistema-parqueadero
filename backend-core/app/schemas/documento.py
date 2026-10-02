import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoDocumento
from app.schemas.usuario import UsuarioRead
from app.schemas.vehiculo import VehiculoRead


class DocumentoRead(BaseModel):
    """No expone ``ruta_archivo``: el archivo se descarga por /documentos/{id}/archivo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: TipoDocumento
    content_type: str
    tamano_bytes: int
    creado_en: datetime


class VehiculoConDocumentos(VehiculoRead):
    documentos: list[DocumentoRead] = []


class UsuarioConDocumentos(UsuarioRead):
    documentos: list[DocumentoRead] = []


class SolicitudVerificacion(BaseModel):
    """Un item de la bandeja del administrador: un estudiante con su carnet y los vehiculos
    pendientes (cada uno con su foto de placa y tarjeta de propiedad)."""

    usuario: UsuarioConDocumentos
    vehiculos: list[VehiculoConDocumentos]


class ResolverVerificacion(BaseModel):
    aprobar: bool
    motivo: str | None = None
