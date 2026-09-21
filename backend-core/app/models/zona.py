import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.acceso import Acceso
    from app.models.espacio import Espacio


class Zona(Base):
    """Fuente de verdad atomica para RN-01 (descuento de cupo) y RN-02 (liberacion de cupo)."""

    __tablename__ = "zonas"
    __table_args__ = (
        CheckConstraint("capacidad_total > 0", name="ck_zonas_capacidad_positiva"),
        CheckConstraint(
            "cupos_disponibles >= 0 AND cupos_disponibles <= capacidad_total",
            name="ck_zonas_cupos_en_rango",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    ubicacion_descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacidad_total: Mapped[int] = mapped_column(Integer, nullable=False)
    cupos_disponibles: Mapped[int] = mapped_column(Integer, nullable=False)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    espacios: Mapped[list["Espacio"]] = relationship(back_populates="zona")
    accesos: Mapped[list["Acceso"]] = relationship(back_populates="zona")
