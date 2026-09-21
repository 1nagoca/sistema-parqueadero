from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.vehiculo import VehiculoCreate, VehiculoRead
from app.services import vehiculo_service

router = APIRouter(prefix="/vehiculos", tags=["vehiculos"])


@router.post("", response_model=VehiculoRead, status_code=status.HTTP_201_CREATED)
def crear_vehiculo(
    datos: VehiculoCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN, RolUsuario.VIGILANTE)),
):
    existe = vehiculo_service.obtener_por_placa(db, datos.placa)
    if existe is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La placa ya esta registrada")
    return vehiculo_service.crear_vehiculo(db, datos)


@router.get("/placa/{placa}", response_model=VehiculoRead)
def buscar_por_placa(
    placa: str,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN, RolUsuario.VIGILANTE)),
):
    vehiculo = vehiculo_service.obtener_por_placa(db, placa)
    if vehiculo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")
    return vehiculo
