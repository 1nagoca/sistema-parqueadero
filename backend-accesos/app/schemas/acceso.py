# Schemas (Pydantic): la forma de los datos que entran y salen por la API de accesos; si no cumplen, responde 422.
import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.enums import TipoAcceso


# Lo que envia el vigilante al registrar una entrada.
class AccesoEntradaCreate(BaseModel):
    vehiculo_id: uuid.UUID
    zona_id: uuid.UUID
    # RN-06: toda entrada ocupa un puesto concreto del plano.
    espacio_id: uuid.UUID
    usuario_id: uuid.UUID | None = None
    tipo_acceso: TipoAcceso = TipoAcceso.NORMAL
    autorizado_por_id: uuid.UUID | None = None
    justificacion: str | None = None
    placa_detectada_por_alpr: bool = False
    confianza_alpr: Decimal | None = None

    # Un visitante exige quien autoriza y la justificacion.
    @model_validator(mode="after")
    def validar_visitante(self) -> "AccesoEntradaCreate":
        """Espejo del CHECK de BD (RN-03): defensa en profundidad, no reemplazo del constraint."""
        if self.tipo_acceso == TipoAcceso.VISITANTE:
            if not self.autorizado_por_id or not self.justificacion:
                raise ValueError(
                    "los accesos de visitante requieren autorizado_por_id y justificacion"
                )
        return self


# Lo que devuelve la API de un acceso.
class AccesoRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vehiculo_id: uuid.UUID
    usuario_id: uuid.UUID | None
    zona_id: uuid.UUID
    espacio_id: uuid.UUID | None
    tipo_acceso: TipoAcceso
    fecha_hora_entrada: datetime
    fecha_hora_salida: datetime | None
    duracion_minutos: int | None
    autorizado_por_id: uuid.UUID | None
    justificacion: str | None
    placa_detectada_por_alpr: bool
    confianza_alpr: Decimal | None


# Un acceso abierto con su placa y el codigo del espacio, para la lista de vehiculos adentro.
class AccesoActivoRead(AccesoRead):
    """AccesoRead + datos denormalizados para listar 'vehiculos adentro' sin N+1 requests."""

    placa: str
    espacio_codigo: str | None = None
