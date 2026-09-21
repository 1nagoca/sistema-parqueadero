import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ZonaBase(BaseModel):
    nombre: str
    ubicacion_descripcion: str | None = None
    capacidad_total: int


class ZonaCreate(ZonaBase):
    pass


class ZonaRead(ZonaBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    cupos_disponibles: int
    activa: bool
    creado_en: datetime
    actualizado_en: datetime
