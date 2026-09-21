import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TipoAcceso

if TYPE_CHECKING:
    from app.models.espacio import Espacio
    from app.models.usuario import Usuario
    from app.models.vehiculo import Vehiculo
    from app.models.zona import Zona

acceso_tipo_enum = ENUM(
    TipoAcceso, name="acceso_tipo_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class Acceso(Base):
    __tablename__ = "accesos"
    __table_args__ = (
        CheckConstraint(
            "fecha_hora_salida IS NULL OR fecha_hora_salida > fecha_hora_entrada",
            name="ck_accesos_salida_posterior_entrada",
        ),
        CheckConstraint(
            "tipo_acceso <> 'visitante' OR "
            "(autorizado_por_id IS NOT NULL AND justificacion IS NOT NULL AND justificacion <> '')",
            name="ck_accesos_visitante_requiere_autorizacion",
        ),
        Index(
            "uq_accesos_vehiculo_activo",
            "vehiculo_id",
            unique=True,
            postgresql_where=text("fecha_hora_salida IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    vehiculo_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehiculos.id", ondelete="RESTRICT"), nullable=False
    )
    # Conductor al momento del ingreso; puede diferir del dueno registrado del vehiculo
    # (ej. prestamo), por eso es una FK independiente de vehiculos.usuario_id.
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    zona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zonas.id", ondelete="RESTRICT"), nullable=False
    )
    espacio_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("espacios.id", ondelete="RESTRICT"), nullable=True
    )
    tipo_acceso: Mapped[TipoAcceso] = mapped_column(
        acceso_tipo_enum, nullable=False, default=TipoAcceso.NORMAL, server_default=TipoAcceso.NORMAL.value
    )
    fecha_hora_entrada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_hora_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duracion_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Vigilante que autoriza el ingreso de un vehiculo de visitante (RN-03).
    autorizado_por_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    placa_detectada_por_alpr: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    confianza_alpr: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vehiculo: Mapped["Vehiculo"] = relationship(back_populates="accesos")
    usuario: Mapped["Usuario | None"] = relationship(
        back_populates="accesos_como_conductor", foreign_keys=[usuario_id]
    )
    autorizado_por: Mapped["Usuario | None"] = relationship(
        back_populates="accesos_autorizados", foreign_keys=[autorizado_por_id]
    )
    zona: Mapped["Zona"] = relationship(back_populates="accesos")
    espacio: Mapped["Espacio | None"] = relationship(back_populates="accesos")
