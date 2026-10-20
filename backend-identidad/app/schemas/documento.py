# Schemas (Pydantic): la forma de los datos que entran y salen por la API de documentos y verificaciones; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import TipoDocumento
from app.schemas.usuario import UsuarioRead
from app.schemas.vehiculo import VehiculoRead


# Datos de un documento subido (sin la ruta del archivo).
class DocumentoRead(BaseModel):
    """No expone ``ruta_archivo``: el archivo se descarga por /documentos/{id}/archivo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tipo: TipoDocumento
    content_type: str
    tamano_bytes: int
    creado_en: datetime


# Un vehiculo junto con sus documentos.
class VehiculoConDocumentos(VehiculoRead):
    documentos: list[DocumentoRead] = []


# Un usuario junto con sus documentos.
class UsuarioConDocumentos(UsuarioRead):
    documentos: list[DocumentoRead] = []


# Un item de la bandeja del administrador.
class SolicitudVerificacion(BaseModel):
    """Un item de la bandeja del administrador: un estudiante con su carnet y los vehiculos
    pendientes (cada uno con su foto de placa y tarjeta de propiedad)."""

    usuario: UsuarioConDocumentos
    vehiculos: list[VehiculoConDocumentos]


# Lo que envia el administrador: aprobar o rechazar, y el motivo si rechaza.
class ResolverVerificacion(BaseModel):
    aprobar: bool
    motivo: str | None = None
