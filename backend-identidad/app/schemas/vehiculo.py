# Schemas (Pydantic): la forma de los datos que entran y salen por la API de vehiculos; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import EstadoVerificacion, TipoVehiculo


# Campos comunes de un vehiculo; la electrica no tiene placa y lleva numero de serie.
class VehiculoBase(BaseModel):
    placa: str | None = Field(default=None, min_length=1, max_length=10)
    tipo_vehiculo: TipoVehiculo
    marca: str | None = None
    modelo: str | None = None
    color: str | None = None
    es_electrica: bool = False
    numero_serie: str | None = None

    # Guarda la placa sin espacios y en mayusculas.
    @field_validator("placa")
    @classmethod
    def normalizar_placa(cls, valor: str | None) -> str | None:
        return valor.strip().upper() if valor is not None else None


# Lo que envia el admin o el vigilante al crear un vehiculo (siempre con placa).
class VehiculoCreate(VehiculoBase):
    placa: str = Field(min_length=1, max_length=10)
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

    # Solo motos de visitantes: la de un estudiante entra por su panel y la revisa el admin.
    @model_validator(mode="after")
    def validar_propietario_o_visitante(self) -> "VehiculoCreate":
        """POST /vehiculos solo registra visitantes; tambien cubre el CHECK de BD
        ck_vehiculos_propietario_o_visitante, que sin esto llegaria a Postgres como 500."""
        if self.usuario_id is not None or not self.es_visitante:
            raise ValueError("solo se registran motos de visitantes: la moto de un estudiante se registra desde su panel")
        return self

    # El visitante no entra con moto electrica: sin esto el CHECK de BD daria 500.
    @model_validator(mode="after")
    def sin_electricas(self) -> "VehiculoCreate":
        if self.es_electrica or self.numero_serie is not None:
            raise ValueError("la moto eléctrica la registra el estudiante desde su panel")
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
