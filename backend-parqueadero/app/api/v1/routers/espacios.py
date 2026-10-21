import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import UsuarioToken, get_current_user, get_db, require_role
from app.models.enums import RolUsuario
from app.models.espacio import Espacio
from app.models.zona import Zona
from app.schemas.espacio import EspacioCreate, EspacioLoteCreate, EspacioLoteResultado, EspacioRead
from app.services import espacio_service

router = APIRouter(prefix="/espacios", tags=["espacios"])


# GET /espacios (cualquier usuario): espacios, opcionalmente de una zona.
@router.get("", response_model=list[EspacioRead])
def listar_espacios(
    zona_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(get_current_user),
):
    """Sin restriccion de rol: alimenta el mismo mapa interactivo que /zonas."""
    consulta = db.query(Espacio)
    if zona_id is not None:
        consulta = consulta.filter(Espacio.zona_id == zona_id)
    return consulta.all()


# POST /espacios (admin): crea un espacio dentro de una zona.
@router.post("", response_model=EspacioRead, status_code=status.HTTP_201_CREATED)
def crear_espacio(
    datos: EspacioCreate,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    espacio = Espacio(**datos.model_dump())
    db.add(espacio)
    db.commit()
    db.refresh(espacio)
    return espacio


# POST /espacios/lote (admin): crea de una vez los puestos del plano que falten en la zona.
@router.post("/lote", response_model=EspacioLoteResultado)
def crear_espacios_lote(
    datos: EspacioLoteCreate,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    if db.get(Zona, datos.zona_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona no encontrada")
    creados = espacio_service.crear_lote(db, datos.zona_id, datos.codigos)
    return EspacioLoteResultado(creados=creados, existentes=len(set(datos.codigos)) - creados)
