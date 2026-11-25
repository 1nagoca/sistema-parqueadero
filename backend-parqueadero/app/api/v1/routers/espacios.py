import logging
import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import UsuarioToken, get_current_user, get_db, require_role
from app.models.enums import RolUsuario
from app.models.espacio import Espacio
from app.models.zona import Zona
from app.schemas.auditoria_parqueadero import AuditoriaParqueaderoPagina, AuditoriaParqueaderoRead
from app.schemas.espacio import EspacioCreate, EspacioLoteCreate, EspacioLoteResultado, EspacioRead
from app.schemas.mantenimiento import MantenimientoCreate, MantenimientoRead
from app.services import auditoria_service, espacio_service, mantenimiento_service, realtime_service

router = APIRouter(prefix="/espacios", tags=["espacios"])
logger = logging.getLogger(__name__)


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


# GET /espacios/mantenimientos (admin): los puestos que estan en mantenimiento ahora, opcionalmente de una zona.
@router.get("/mantenimientos", response_model=list[MantenimientoRead])
def listar_mantenimientos(
    zona_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    return mantenimiento_service.listar_activos(db, zona_id)


# GET /espacios/auditoria (admin): trazas del parqueadero entre dos fechas (por defecto el semestre actual), paginadas.
@router.get("/auditoria", response_model=AuditoriaParqueaderoPagina)
def listar_auditoria(
    desde: date | None = None,
    hasta: date | None = None,
    tabla_afectada: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
) -> AuditoriaParqueaderoPagina:
    """Solo lectura: las trazas las escribe unicamente mantenimiento_service y no hay rutas para
    cambiarlas ni borrarlas."""
    try:
        desde, hasta = auditoria_service.resolver_rango(desde, hasta)
    except auditoria_service.RangoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    trazas, total = auditoria_service.listar_auditoria(
        db, desde=desde, hasta=hasta, tabla_afectada=tabla_afectada, pagina=pagina, por_pagina=por_pagina
    )
    return AuditoriaParqueaderoPagina(
        items=[AuditoriaParqueaderoRead.model_validate(traza) for traza in trazas],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        desde=desde,
        hasta=hasta,
    )


# POST /espacios/{id}/mantenimiento (admin): pone un puesto libre en mantenimiento y baja un cupo de la zona.
@router.post("/{espacio_id}/mantenimiento", response_model=EspacioRead)
def poner_en_mantenimiento(
    espacio_id: uuid.UUID,
    datos: MantenimientoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    try:
        espacio, zona = mantenimiento_service.poner_en_mantenimiento(db, espacio_id, datos.motivo, admin.id)
    except _ERRORES_DE_MANTENIMIENTO as exc:
        db.rollback()
        raise _error_http(exc) from exc
    return _confirmar(db, espacio, zona, background_tasks, "en mantenimiento")


# POST /espacios/{id}/habilitar (admin): devuelve a libre un puesto en mantenimiento y sube un cupo de la zona.
@router.post("/{espacio_id}/habilitar", response_model=EspacioRead)
def habilitar_espacio(
    espacio_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    admin: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    try:
        espacio, zona = mantenimiento_service.habilitar(db, espacio_id, admin.id)
    except _ERRORES_DE_MANTENIMIENTO as exc:
        db.rollback()
        raise _error_http(exc) from exc
    return _confirmar(db, espacio, zona, background_tasks, "habilitado")


# Errores del servicio que se traducen a 404 o 409.
_ERRORES_DE_MANTENIMIENTO = (
    mantenimiento_service.EspacioNoEncontradoError,
    mantenimiento_service.EstadoNoPermitidoError,
    mantenimiento_service.ZonaSinCupoError,
)


# Puesto que no existe: 404; estado o cupo que no lo permiten: 409.
def _error_http(exc: Exception) -> HTTPException:
    if isinstance(exc, mantenimiento_service.EspacioNoEncontradoError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


# Guarda el cambio, avisa al mapa por /ws/zonas despues de responder y lo deja en la consola.
def _confirmar(
    db: Session, espacio: Espacio, zona: Zona, background_tasks: BackgroundTasks, accion: str
) -> Espacio:
    db.commit()
    db.refresh(espacio)
    db.refresh(zona)
    background_tasks.add_task(realtime_service.broadcast_actualizacion_zona, zona.id, zona.cupos_disponibles)
    logger.info(
        "Parqueadero: puesto %s %s en %s; quedan %s de %s cupos",
        espacio.codigo,
        accion,
        zona.nombre,
        zona.cupos_disponibles,
        zona.capacidad_total,
    )
    return espacio
