import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.enums import AccionAuditoria


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
