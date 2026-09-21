from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.models.zona import Zona
from app.schemas.zona import ZonaCreate, ZonaRead

router = APIRouter(prefix="/zonas", tags=["zonas"])


@router.get("", response_model=list[ZonaRead])
def listar_zonas(db: Session = Depends(get_db), _: Usuario = Depends(get_current_user)):
    """Sin restriccion de rol: alimenta el mapa interactivo que ve cualquier usuario autenticado."""
    return db.query(Zona).filter(Zona.activa.is_(True)).all()


@router.post("", response_model=ZonaRead, status_code=status.HTTP_201_CREATED)
def crear_zona(
    datos: ZonaCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    zona = Zona(**datos.model_dump(), cupos_disponibles=datos.capacidad_total)
    db.add(zona)
    db.commit()
    db.refresh(zona)
    return zona
