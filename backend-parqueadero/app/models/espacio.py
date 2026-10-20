import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import EstadoEspacio

if TYPE_CHECKING:
    from app.models.zona import Zona

# Usa el tipo ENUM que ya creo la migracion (create_type=False).
espacio_estado_enum = ENUM(
    EstadoEspacio, name="espacio_estado_enum", create_type=False, values_callable=lambda e: [m.value for m in e]
)


# Tabla espacios: cada puesto de una zona con su estado.
class Espacio(Base):
    """Espacio fisico individual dentro de una zona; su ``estado`` alimenta el mapa con
    colores (libre=verde, ocupado=rojo, reservado/mantenimiento=amarillo). Zonas que solo
    llevan conteo agregado (sin mapa granular) simplemente no tienen filas aqui."""

    __tablename__ = "espacios"
    # El codigo no se repite dentro de la misma zona.
    __table_args__ = (UniqueConstraint("zona_id", "codigo", name="uq_espacios_zona_codigo"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    zona_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("zonas.id", ondelete="RESTRICT"), nullable=False
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    estado: Mapped[EstadoEspacio] = mapped_column(
        espacio_estado_enum, nullable=False, default=EstadoEspacio.LIBRE, server_default=EstadoEspacio.LIBRE.value
    )
    tipo_espacio: Mapped[str | None] = mapped_column(String(20), nullable=True)
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actualizado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relacion: la zona a la que pertenece.
    zona: Mapped["Zona"] = relationship(back_populates="espacios")
