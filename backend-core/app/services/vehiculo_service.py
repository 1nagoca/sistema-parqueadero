from sqlalchemy.orm import Session

from app.models.vehiculo import Vehiculo
from app.schemas.vehiculo import VehiculoCreate


def crear_vehiculo(db: Session, datos: VehiculoCreate) -> Vehiculo:
    vehiculo = Vehiculo(**datos.model_dump())
    db.add(vehiculo)
    db.commit()
    db.refresh(vehiculo)
    return vehiculo


def obtener_por_placa(db: Session, placa: str) -> Vehiculo | None:
    return db.query(Vehiculo).filter(Vehiculo.placa == placa.strip().upper()).first()
