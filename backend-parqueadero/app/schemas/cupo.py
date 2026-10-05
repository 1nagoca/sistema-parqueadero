import uuid

from pydantic import BaseModel, ConfigDict


class CupoSolicitud(BaseModel):
    zona_id: uuid.UUID
    espacio_id: uuid.UUID | None = None


class EspacioCodigo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
