import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.acceso import Acceso
from app.models.enums import RolUsuario
from app.models.espacio import Espacio
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.models.zona import Zona
from app.schemas.acceso import AccesoActivoRead, AccesoEntradaCreate, AccesoRead
from app.services import acceso_service, realtime_service, vehiculo_service
from app.services.zona_service import EspacioNoDisponibleError, SinCuposDisponiblesError

router = APIRouter(prefix="/accesos", tags=["accesos"])


@router.get("", response_model=list[AccesoActivoRead])
def listar_accesos_activos(
    zona_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    """Vehiculos actualmente adentro (sin fecha_hora_salida), para que el vigilante pueda
    registrar la salida sin tener que recordar/escribir la placa de nuevo."""
    consulta = (
        db.query(Acceso, Vehiculo.placa, Espacio.codigo)
        .join(Vehiculo, Vehiculo.id == Acceso.vehiculo_id)
        .outerjoin(Espacio, Espacio.id == Acceso.espacio_id)
        .filter(Acceso.fecha_hora_salida.is_(None))
    )
    if zona_id is not None:
        consulta = consulta.filter(Acceso.zona_id == zona_id)
    consulta = consulta.order_by(Acceso.fecha_hora_entrada)

    return [
        AccesoActivoRead(
            **AccesoRead.model_validate(acceso).model_dump(),
            placa=placa,
            espacio_codigo=espacio_codigo,
        )
        for acceso, placa, espacio_codigo in consulta.all()
    ]


@router.get("/buscar", response_model=AccesoRead)
def buscar_acceso_activo(
    placa: str,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    """Usado por el panel de vigilancia para saber si una placa tiene un acceso abierto
    (y por lo tanto corresponde ofrecer 'registrar salida' en vez de una nueva entrada)."""
    vehiculo = vehiculo_service.obtener_por_placa(db, placa)
    if vehiculo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")

    acceso = (
        db.query(Acceso)
        .filter(Acceso.vehiculo_id == vehiculo.id, Acceso.fecha_hora_salida.is_(None))
        .first()
    )
    if acceso is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay un acceso activo para esa placa")
    return acceso


@router.post("/entrada", response_model=AccesoRead, status_code=status.HTTP_201_CREATED)
def registrar_entrada(
    datos: AccesoEntradaCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    vigilante: Usuario = Depends(require_role(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    try:
        acceso = acceso_service.registrar_entrada(db, datos, realizado_por_id=vigilante.id)
    except (SinCuposDisponiblesError, EspacioNoDisponibleError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    _programar_broadcast(background_tasks, db, acceso)
    return acceso


@router.post("/{acceso_id}/salida", response_model=AccesoRead)
def registrar_salida(
    acceso_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    vigilante: Usuario = Depends(require_role(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    try:
        acceso = acceso_service.registrar_salida(db, acceso_id, realizado_por_id=vigilante.id)
    except acceso_service.AccesoNoEncontradoOYaCerradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    _programar_broadcast(background_tasks, db, acceso)
    return acceso


def _programar_broadcast(background_tasks: BackgroundTasks, db: Session, acceso: Acceso) -> None:
    """Envia el estado fresco de la zona por /ws/zonas despues de responder, para que el mapa
    de usuarios se actualice sin polling. Se agenda como BackgroundTask porque el broadcast es
    async y acceso_service/zona_service son sincronos (SQLAlchemy Session clasica)."""
    zona = db.get(Zona, acceso.zona_id)
    if zona is not None:
        background_tasks.add_task(
            realtime_service.broadcast_actualizacion_zona, zona.id, zona.cupos_disponibles
        )
