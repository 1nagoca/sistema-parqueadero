import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import AccionAuditoria

auditoria_accion_enum = ENUM(
    AccionAuditoria, name="auditoria_accion_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class AuditoriaAcceso(Base):
    """Traza inmutable de RN-04. Append-only por permisos de base de datos (ver migracion
    inicial: REVOKE UPDATE, DELETE ON auditoria_accesos), no solo por convencion de la app."""

    __tablename__ = "auditoria_accesos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    tabla_afectada: Mapped[str] = mapped_column(String(50), nullable=False)
    # Referencia polimorfica (accesos, espacios, zonas); sin FK formal porque apunta a varias tablas.
    registro_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    accion: Mapped[AccionAuditoria] = mapped_column(auditoria_accion_enum, nullable=False)
    valores_anteriores: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    valores_nuevos: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # Usuario del servicio de identidad: solo su identificador, sin llave foranea.
    realizado_por_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    motivo: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_hora: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    ip_origen: Mapped[str | None] = mapped_column(String(45), nullable=True)
