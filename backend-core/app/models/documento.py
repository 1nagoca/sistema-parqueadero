import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import TipoDocumento

if TYPE_CHECKING:
    from app.models.usuario import Usuario
    from app.models.vehiculo import Vehiculo

tipo_documento_enum = ENUM(
    TipoDocumento, name="documento_tipo_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


class Documento(Base):
    """Imagen/PDF de soporte para la verificacion: el carnet cuelga del usuario; la foto de la
    placa y la tarjeta de propiedad cuelgan del vehiculo. El archivo vive en el almacenamiento
    privado (``settings.UPLOAD_DIR``), nunca en una ruta publica."""

    __tablename__ = "documentos"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False
    )
    vehiculo_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehiculos.id", ondelete="CASCADE"), nullable=True
    )
    tipo: Mapped[TipoDocumento] = mapped_column(tipo_documento_enum, nullable=False)
    ruta_archivo: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    tamano_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    usuario: Mapped["Usuario"] = relationship(back_populates="documentos")
    vehiculo: Mapped["Vehiculo | None"] = relationship(back_populates="documentos")
