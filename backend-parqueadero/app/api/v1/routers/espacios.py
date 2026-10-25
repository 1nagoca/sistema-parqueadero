import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import UsuarioToken, get_current_user, get_db, require_role
from app.models.enums import RolUsuario
from app.models.espacio import Espacio
from app.models.zona import Zona
from app.schemas.espacio import EspacioCreate, EspacioLoteCreate, EspacioLoteResultado, EspacioRead
from app.services import espacio_service, realtime_service

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


# POST /espacios/lote (admin): crea de una vez los puestos del plano que falten en la zona y ajusta su capacidad.
@router.post("/lote", response_model=EspacioLoteResultado)
def crear_espacios_lote(
    datos: EspacioLoteCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    zona = db.get(Zona, datos.zona_id)
    if zona is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Zona no encontrada")
    creados, zona_ajustada = espacio_service.crear_lote(db, datos.zona_id, datos.codigos)
    # Si hubo puestos nuevos o cambio la capacidad, avisa al mapa por /ws/zonas despues de responder.
    if creados > 0 or zona_ajustada is not None:
        if zona_ajustada is None:
            db.refresh(zona)
        aviso = zona_ajustada or zona
        background_tasks.add_task(realtime_service.broadcast_actualizacion_zona, aviso.id, aviso.cupos_disponibles)
    return EspacioLoteResultado(creados=creados, existentes=len(set(datos.codigos)) - creados)
