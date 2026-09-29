import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

    @model_validator(mode="after")
    def validar_propietario_o_visitante(self) -> "VehiculoCreate":
        """Espejo del CHECK de BD ck_vehiculos_propietario_o_visitante: sin esto la violacion
        llega hasta Postgres y la API responde 500 en vez de 422."""
        if self.usuario_id is None and not self.es_visitante:
            raise ValueError("el vehiculo requiere usuario_id o es_visitante=true")
        return self


class VehiculoRead(VehiculoBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    usuario_id: uuid.UUID | None
    es_visitante: bool
    creado_en: datetime
