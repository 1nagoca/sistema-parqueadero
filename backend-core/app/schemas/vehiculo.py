import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import TipoVehiculo


class VehiculoBase(BaseModel):
    placa: str = Field(min_length=1, max_length=10)
    tipo_vehiculo: TipoVehiculo
    marca: str | None = None
    modelo: str | None = None
    color: str | None = None

    @field_validator("placa")
    @classmethod
    def normalizar_placa(cls, valor: str) -> str:
        return valor.strip().upper()


class VehiculoCreate(VehiculoBase):
    usuario_id: uuid.UUID | None = None
    es_visitante: bool = False


class VehiculoRead(VehiculoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID | None
    es_visitante: bool
    creado_en: datetime
