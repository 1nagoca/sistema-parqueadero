# Schemas (Pydantic): la forma de los datos que entran y salen por la API interna (/interno), que solo usa el servicio de accesos; si no cumplen, responde 422.
import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import EstadoVerificacion, RolUsuario


# Del dueno solo se comparte el id, si esta aprobado y si sigue activo.
class PropietarioInterno(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado_verificacion: EstadoVerificacion
    activo: bool


# Lo minimo de un vehiculo para decidir si puede entrar.
class VehiculoInterno(BaseModel):
    """Lo que accesos necesita para registrar una entrada. Sin nombres, correos ni documentos."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    placa: str
    es_visitante: bool
    estado_verificacion: EstadoVerificacion
    propietario: PropietarioInterno | None


# Lo minimo de un usuario para saber que existe.
class UsuarioInterno(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rol: RolUsuario
    activo: bool
