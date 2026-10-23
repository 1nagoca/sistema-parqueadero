# Schemas (Pydantic): la forma de los datos que entran y salen por la API de auditoria; si no cumplen, responde 422.
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccionAuditoria


# Una traza de la bitacora de entradas y salidas.
class AuditoriaAccesoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tabla_afectada: str
    registro_id: uuid.UUID
    accion: AccionAuditoria
    valores_anteriores: dict[str, Any] | None
    valores_nuevos: dict[str, Any] | None
    realizado_por_id: uuid.UUID
    motivo: str | None
    fecha_hora: datetime
    ip_origen: str | None


# Una pagina de la bitacora con el rango de fechas que se consulto.
class AuditoriaAccesoPagina(BaseModel):
    items: list[AuditoriaAccesoRead]
    total: int
    pagina: int
    por_pagina: int
    desde: date
    hasta: date
