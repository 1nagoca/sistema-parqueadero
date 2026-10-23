import uuid
from pathlib import Path
from typing import NamedTuple

from sqlalchemy.orm import Session

from app.models.documento import Documento
from app.models.enums import EstadoVerificacion, TipoDocumento
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.vehiculo import VehiculoCreate
from app.services import documento_service


class PropietarioNoVisibleError(Exception):
    """El vigilante no puede ver al dueno de esa placa (no se dice por que)."""


# El carnet que se le puede mostrar al vigilante: ruta real y tipo del archivo.
class CarnetVisible(NamedTuple):
    ruta: Path
    content_type: str


# Crea un vehiculo y lo guarda en la base.
def crear_vehiculo(db: Session, datos: VehiculoCreate) -> Vehiculo:
    vehiculo = Vehiculo(**datos.model_dump())
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)
    return vehiculo


# Busca un vehiculo por placa (sin espacios y en mayusculas).
def obtener_por_placa(db: Session, placa: str) -> Vehiculo | None:
    return db.query(Vehiculo).filter(Vehiculo.placa == placa.strip().upper()).first()


# Dueno de la moto y su carnet si el vigilante puede verlos (RN-09); si no, PropietarioNoVisibleError.
def propietario_para_vigilante(db: Session, placa: str) -> tuple[Usuario, CarnetVisible | None]:
    """Solo motos registradas y aprobadas cuyo dueno esta aprobado y activo; todo lo demas
    responde igual para no revelar el estado de motos o duenos."""
    vehiculo = obtener_por_placa(db, placa)
    if (
        vehiculo is None
        or vehiculo.es_visitante
        or vehiculo.usuario is None
        or vehiculo.estado_verificacion != EstadoVerificacion.APROBADO
    ):
        raise PropietarioNoVisibleError("Propietario no disponible")
    dueno = vehiculo.usuario
    if not dueno.activo or dueno.estado_verificacion != EstadoVerificacion.APROBADO:
        raise PropietarioNoVisibleError("Propietario no disponible")
    return dueno, _carnet_en_disco(db, dueno.id)


# El carnet mas reciente del dueno si el archivo esta en disco.
def _carnet_en_disco(db: Session, usuario_id: uuid.UUID) -> CarnetVisible | None:
    carnet = (
        db.query(Documento)
        .filter(
            Documento.usuario_id == usuario_id,
            Documento.tipo == TipoDocumento.CARNET,
            Documento.vehiculo_id.is_(None),
        )
        .order_by(Documento.creado_en.desc())
        .first()
    )
    if carnet is None:
        return None
    try:
        ruta = documento_service.ruta_absoluta(carnet.ruta_archivo)
    except documento_service.ArchivoInvalidoError:
        return None
    return CarnetVisible(ruta, carnet.content_type) if ruta.is_file() else None
