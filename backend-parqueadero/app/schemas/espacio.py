# Schemas (Pydantic): la forma de los datos que entran y salen por la API de espacios; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import EstadoEspacio


# Campos comunes de un espacio.
class EspacioBase(BaseModel):
    codigo: str
    tipo_espacio: str | None = None


# Lo que envia el admin al crear un espacio.
class EspacioCreate(EspacioBase):
    zona_id: uuid.UUID


# Lo que devuelve la API de un espacio.
class EspacioRead(EspacioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zona_id: uuid.UUID
    estado: EstadoEspacio
    creado_en: datetime
    actualizado_en: datetime


# Lo que envia el admin para crear de una vez los puestos del plano.
class EspacioLoteCreate(BaseModel):
    zona_id: uuid.UUID
    codigos: list[str] = Field(min_length=1, max_length=1000)

    # Cada codigo sin espacios, en mayusculas y de hasta 20 caracteres.
    @field_validator("codigos")
    @classmethod
    def normalizar_codigos(cls, valores: list[str]) -> list[str]:
        codigos = [valor.strip().upper() for valor in valores]
        if any(not codigo or len(codigo) > 20 for codigo in codigos):
            raise ValueError("cada codigo debe tener entre 1 y 20 caracteres")
        return codigos


# Cuantos puestos se crearon y cuantos ya existian.
class EspacioLoteResultado(BaseModel):
    creados: int
    existentes: int
