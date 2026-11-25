# Schemas (Pydantic): la forma de las trazas que salen por la API de auditoria del parqueadero.
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccionAuditoria


# Una traza de la bitacora del parqueadero (hoy, el mantenimiento de puestos).
class AuditoriaParqueaderoRead(BaseModel):
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
class AuditoriaParqueaderoPagina(BaseModel):
    items: list[AuditoriaParqueaderoRead]
    total: int
    pagina: int
    por_pagina: int
    desde: date
    hasta: date
