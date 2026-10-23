# Schemas (Pydantic): la forma de los datos que entran y salen por la API de vehiculos; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EstadoVerificacion, TipoVehiculo


# Campos comunes de un vehiculo.
class VehiculoBase(BaseModel):
    placa: str = Field(min_length=1, max_length=10)
    tipo_vehiculo: TipoVehiculo
    marca: str | None = None
    modelo: str | None = None
    color: str | None = None

    # Guarda la placa sin espacios y en mayusculas.
    @field_validator("placa")
    @classmethod
    def normalizar_placa(cls, valor: str) -> str:
        return valor.strip().upper()


# Lo que envia el admin o el vigilante al crear un vehiculo.
class VehiculoCreate(VehiculoBase):
    tipo_vehiculo: TipoVehiculo = TipoVehiculo.MOTO
    usuario_id: uuid.UUID | None = None
    es_visitante: bool = False

    # El parqueadero solo recibe motos.
    @field_validator("tipo_vehiculo")
    @classmethod
    def solo_motos(cls, valor: TipoVehiculo) -> TipoVehiculo:
        if valor != TipoVehiculo.MOTO:
            raise ValueError("solo se registran motos")
        return valor

    # Debe tener dueno o ser de visitante.
    @model_validator(mode="after")
    def validar_propietario_o_visitante(self) -> "VehiculoCreate":
        """Espejo del CHECK de BD ck_vehiculos_propietario_o_visitante: sin esto la violacion
        llega hasta Postgres y la API responde 500 en vez de 422."""
        if self.usuario_id is None and not self.es_visitante:
            raise ValueError("el vehiculo requiere usuario_id o es_visitante=true")
        return self


# Lo que devuelve la API de un vehiculo.
class VehiculoRead(VehiculoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID | None
    es_visitante: bool
    estado_verificacion: EstadoVerificacion
    motivo_rechazo: str | None
    creado_en: datetime


# Lo que ve el vigilante del dueno de una moto al buscar su placa (RN-09): sin correo, documento, telefono ni ids.
class PropietarioVigilante(BaseModel):
    nombre_completo: str
    tiene_carnet: bool
