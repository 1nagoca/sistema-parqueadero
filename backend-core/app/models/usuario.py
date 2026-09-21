import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import RolUsuario

if TYPE_CHECKING:
    from app.models.acceso import Acceso
    from app.models.auditoria_acceso import AuditoriaAcceso
    from app.models.vehiculo import Vehiculo

rol_usuario_enum = ENUM(
    RolUsuario, name="usuario_rol_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    nombre_completo: Mapped[str] = mapped_column(String(150), nullable=False)
    correo_institucional: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    documento_identidad: Mapped[str] = mapped_column(String(30), nullable=False, unique=True)
    telefono: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rol: Mapped[RolUsuario] = mapped_column(rol_usuario_enum, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    vehiculos: Mapped[list["Vehiculo"]] = relationship(
        back_populates="usuario", foreign_keys="Vehiculo.usuario_id"
    )
    accesos_como_conductor: Mapped[list["Acceso"]] = relationship(
        back_populates="usuario", foreign_keys="Acceso.usuario_id"
    )
    accesos_autorizados: Mapped[list["Acceso"]] = relationship(
        back_populates="autorizado_por", foreign_keys="Acceso.autorizado_por_id"
    )
    auditorias: Mapped[list["AuditoriaAcceso"]] = relationship(back_populates="realizado_por")
