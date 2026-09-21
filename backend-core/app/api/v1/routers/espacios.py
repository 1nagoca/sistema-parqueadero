import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.enums import RolUsuario
from app.models.espacio import Espacio
from app.models.usuario import Usuario
from app.schemas.espacio import EspacioCreate, EspacioRead

router = APIRouter(prefix="/espacios", tags=["espacios"])


@router.get("", response_model=list[EspacioRead])
def listar_espacios(
    zona_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(get_current_user),
):
    """Sin restriccion de rol: alimenta el mismo mapa interactivo que /zonas."""
    consulta = db.query(Espacio)
    if zona_id is not None:
        consulta = consulta.filter(Espacio.zona_id == zona_id)
    return consulta.all()


@router.post("", response_model=EspacioRead, status_code=status.HTTP_201_CREATED)
def crear_espacio(
    datos: EspacioCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    espacio = Espacio(**datos.model_dump())
    db.add(espacio)
    db.commit()
    db.refresh(espacio)
    return espacio
