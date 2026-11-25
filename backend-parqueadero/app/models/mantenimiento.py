import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# Tabla mantenimientos: bitacora de lo que esta en mantenimiento ahora (al habilitar, la fila se borra).
class Mantenimiento(Base):
    """Un puesto en mantenimiento, quien lo puso, por que y desde cuando. La historia completa
    queda en auditoria_parqueadero."""

    __tablename__ = "mantenimientos"
    # Un puesto aparece una sola vez; el motivo va de 3 a 200 caracteres (migracion 0003).
    __table_args__ = (
        UniqueConstraint("espacio_id", name="uq_mantenimientos_espacio_id"),
        CheckConstraint("char_length(motivo) BETWEEN 3 AND 200", name="ck_mantenimientos_motivo_largo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    espacio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("espacios.id", ondelete="RESTRICT", name="fk_mantenimientos_espacio_id"),
        nullable=False,
    )
    motivo: Mapped[str] = mapped_column(String(200), nullable=False)
    # Usuario del servicio de identidad: solo su identificador, sin llave foranea.
    iniciado_por_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    inicio: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
