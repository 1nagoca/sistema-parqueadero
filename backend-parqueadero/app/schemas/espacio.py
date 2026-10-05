import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import EstadoEspacio


class EspacioBase(BaseModel):
    codigo: str
    tipo_espacio: str | None = None


class EspacioCreate(EspacioBase):
    zona_id: uuid.UUID


class EspacioRead(EspacioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    zona_id: uuid.UUID
    estado: EstadoEspacio
    creado_en: datetime
    actualizado_en: datetime
