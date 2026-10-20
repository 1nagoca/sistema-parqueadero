# Schemas (Pydantic): la forma de los datos que entran y salen por la API interna (/interno), que solo usa el servicio de accesos; si no cumplen, responde 422.
import uuid

from pydantic import BaseModel, ConfigDict


# Que zona (y que espacio, si aplica) ocupar o liberar.
class CupoSolicitud(BaseModel):
    zona_id: uuid.UUID
    espacio_id: uuid.UUID | None = None


# El id de un espacio y su codigo visible (por ejemplo A-01).
class EspacioCodigo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    codigo: str
