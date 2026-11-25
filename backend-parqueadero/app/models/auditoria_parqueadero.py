import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AccionAuditoria

# Usa el tipo ENUM que ya creo la migracion (create_type=False).
auditoria_accion_enum = ENUM(
    AccionAuditoria, name="auditoria_accion_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


# Tabla auditoria_parqueadero: trazas de este servicio (solo se agregan filas).
class AuditoriaParqueadero(Base):
    """Mismas columnas que auditoria_accesos. Solo se agregan filas por convencion de la app; el
    REVOKE va con el Paso 7."""

    __tablename__ = "auditoria_parqueadero"
    # Indices que crea la migracion 0003.
    __table_args__ = (
        Index("idx_auditoria_parqueadero_registro", "tabla_afectada", "registro_id"),
        Index("idx_auditoria_parqueadero_fecha_hora", "fecha_hora"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tabla_afectada: Mapped[str] = mapped_column(String(50), nullable=False)
    # Id del registro que cambio (en el mantenimiento, el del espacio); sin FK.
    registro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    accion: Mapped[AccionAuditoria] = mapped_column(auditoria_accion_enum, nullable=False)
    # Como estaba y como quedo el registro (en JSON).
    valores_anteriores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    valores_nuevos: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Usuario del servicio de identidad: solo su identificador, sin llave foranea.
    realizado_por_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip_origen: Mapped[str | None] = mapped_column(String(45), nullable=True)
