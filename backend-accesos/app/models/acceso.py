import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import TipoAcceso

acceso_tipo_enum = ENUM(
    TipoAcceso, name="acceso_tipo_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class Acceso(Base):
    __tablename__ = "accesos"
    __table_args__ = (
        CheckConstraint("placa = upper(placa)", name="ck_accesos_placa_mayusculas"),
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
    # Vehiculo y usuarios pertenecen al servicio de identidad: aqui solo se guarda su
    # identificador, sin llave foranea.
    vehiculo_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # Copia de la placa al registrar la entrada: la lista de vehiculos adentro, la busqueda
    # por placa y las salidas no dependen de identidad.
    placa: Mapped[str] = mapped_column(String(10), nullable=False)
    # Conductor al momento del ingreso; puede diferir del dueno registrado del vehiculo
    # (ej. prestamo).
    usuario_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # Zona y espacio viven en la base de datos del servicio de parqueadero: aqui solo se
    # guarda su identificador, sin llave foranea.
    zona_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    espacio_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tipo_acceso: Mapped[TipoAcceso] = mapped_column(
        acceso_tipo_enum, nullable=False, default=TipoAcceso.NORMAL, server_default=TipoAcceso.NORMAL.value
    )
    fecha_hora_entrada: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    fecha_hora_salida: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duracion_minutos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Vigilante que autoriza el ingreso de un vehiculo de visitante (RN-03).
    autorizado_por_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    justificacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    placa_detectada_por_alpr: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    confianza_alpr: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
