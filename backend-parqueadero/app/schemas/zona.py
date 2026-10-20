# Schemas (Pydantic): la forma de los datos que entran y salen por la API de zonas; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


# Campos comunes de una zona.
class ZonaBase(BaseModel):
    nombre: str
    ubicacion_descripcion: str | None = None
    capacidad_total: int


# Lo que envia el admin al crear una zona.
class ZonaCreate(ZonaBase):
    pass


# Lo que devuelve la API de una zona, con sus cupos disponibles.
class ZonaRead(ZonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cupos_disponibles: int
    activa: bool
    creado_en: datetime
    actualizado_en: datetime
