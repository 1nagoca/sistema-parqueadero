from sqlalchemy.orm import Session

from app.models.vehiculo import Vehiculo
from app.schemas.vehiculo import VehiculoCreate


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
