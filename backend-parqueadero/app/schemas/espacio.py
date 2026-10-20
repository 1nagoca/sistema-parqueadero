# Schemas (Pydantic): la forma de los datos que entran y salen por la API de espacios; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

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
