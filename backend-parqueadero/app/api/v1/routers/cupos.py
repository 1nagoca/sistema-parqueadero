import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.espacio import Espacio
from app.models.zona import Zona
from app.schemas.cupo import CupoSolicitud, EspacioCodigo
from app.schemas.zona import ZonaRead
from app.services import realtime_service, zona_service

# API interna entre microservicios: la usa el servicio de accesos al registrar entradas y
# salidas. El gateway no publica /interno, asi que no es alcanzable desde el navegador.
router = APIRouter(prefix="/interno", tags=["interno"])


@router.post("/cupos/ocupar", response_model=ZonaRead)
def ocupar_cupo(datos: CupoSolicitud, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        zona = zona_service.ocupar_cupo(db, datos.zona_id, datos.espacio_id)
    except (zona_service.SinCuposDisponiblesError, zona_service.EspacioNoDisponibleError) as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _confirmar_y_avisar(db, zona, background_tasks)


@router.post("/cupos/liberar", response_model=ZonaRead)
def liberar_cupo(datos: CupoSolicitud, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    try:
        zona = zona_service.liberar_cupo(db, datos.zona_id, datos.espacio_id)
    except zona_service.ZonaEnCapacidadTotalError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _confirmar_y_avisar(db, zona, background_tasks)


@router.get("/espacios", response_model=list[EspacioCodigo])
def codigos_de_espacios(id: list[uuid.UUID] = Query(default=[]), db: Session = Depends(get_db)):
    """Para que accesos muestre el codigo del espacio sin leer esta base de datos."""
    if not id:
        return []
    return db.query(Espacio).filter(Espacio.id.in_(id)).all()


def _confirmar_y_avisar(db: Session, zona: Zona, background_tasks: BackgroundTasks) -> Zona:
    """Envia el estado fresco de la zona por /ws/zonas despues de responder, para que el mapa
    de usuarios se actualice sin polling."""
    db.commit()
    db.refresh(zona)
    background_tasks.add_task(realtime_service.broadcast_actualizacion_zona, zona.id, zona.cupos_disponibles)
    return zona
