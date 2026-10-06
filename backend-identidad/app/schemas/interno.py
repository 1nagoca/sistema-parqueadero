import uuid

from pydantic import BaseModel, ConfigDict

from app.models.enums import EstadoVerificacion, RolUsuario


class PropietarioInterno(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    estado_verificacion: EstadoVerificacion


class VehiculoInterno(BaseModel):
    """Lo que accesos necesita para registrar una entrada. Sin nombres, correos ni documentos."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    placa: str
    es_visitante: bool
    estado_verificacion: EstadoVerificacion
    propietario: PropietarioInterno | None


class UsuarioInterno(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rol: RolUsuario
    activo: bool
