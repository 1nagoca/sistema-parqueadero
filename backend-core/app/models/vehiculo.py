import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.usuario import estado_verificacion_enum
from app.models.enums import EstadoVerificacion, TipoVehiculo

if TYPE_CHECKING:
    from app.models.acceso import Acceso
    from app.models.documento import Documento
    from app.models.usuario import Usuario

tipo_vehiculo_enum = ENUM(
    TipoVehiculo, name="vehiculo_tipo_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class Vehiculo(Base):
    __tablename__ = "vehiculos"
    __table_args__ = (
        CheckConstraint("placa = upper(placa)", name="ck_vehiculos_placa_mayusculas"),
        CheckConstraint(
            "usuario_id IS NOT NULL OR es_visitante = true",
            name="ck_vehiculos_propietario_o_visitante",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    placa: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    tipo_vehiculo: Mapped[TipoVehiculo] = mapped_column(tipo_vehiculo_enum, nullable=False)
    marca: Mapped[str | None] = mapped_column(String(50), nullable=True)
    modelo: Mapped[str | None] = mapped_column(String(50), nullable=True)
    color: Mapped[str | None] = mapped_column(String(30), nullable=True)
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=True
    )
    es_visitante: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    estado_verificacion: Mapped[EstadoVerificacion] = mapped_column(
        estado_verificacion_enum,
        nullable=False,
        default=EstadoVerificacion.APROBADO,
        server_default=EstadoVerificacion.APROBADO.value,
    )
    motivo_rechazo: Mapped[str | None] = mapped_column(Text, nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped["Usuario | None"] = relationship(back_populates="vehiculos", foreign_keys=[usuario_id])
    accesos: Mapped[list["Acceso"]] = relationship(back_populates="vehiculo")
    documentos: Mapped[list["Documento"]] = relationship(back_populates="vehiculo", cascade="all, delete-orphan")
