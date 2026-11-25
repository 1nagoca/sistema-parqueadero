# Schemas (Pydantic): lo que entra y sale por las rutas de mantenimiento de puestos; si no cumple, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# Lo que envia el admin al poner un puesto en mantenimiento: el motivo es obligatorio.
class MantenimientoCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    motivo: str = Field(min_length=3, max_length=200)


# Un puesto que esta en mantenimiento ahora.
class MantenimientoRead(BaseModel):
    espacio_id: uuid.UUID
    codigo: str
    zona_id: uuid.UUID
    motivo: str
    inicio: datetime
    iniciado_por_id: uuid.UUID
