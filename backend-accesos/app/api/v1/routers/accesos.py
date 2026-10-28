import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import UsuarioToken, get_db, require_role_token
from app.identidad_client.client import IdentidadNoDisponibleError, VehiculoNoEncontradoError
from app.models.acceso import Acceso
from app.models.enums import RolUsuario
from app.schemas.acceso import AccesoActivoRead, AccesoEntradaCreate, AccesoRead
from app.parqueadero_client import client as parqueadero_client
from app.parqueadero_client.client import CupoNoDisponibleError, ParqueaderoNoDisponibleError
from app.services import acceso_service

router = APIRouter(prefix="/accesos", tags=["accesos"])
logger = logging.getLogger(__name__)


# GET /accesos (vigilante, admin): vehiculos que estan adentro, con el codigo de su espacio.
@router.get("", response_model=list[AccesoActivoRead])
def listar_accesos_activos(
    zona_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role_token(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    """Vehiculos actualmente adentro (sin fecha_hora_salida), para que el vigilante pueda
    registrar la salida sin tener que recordar/escribir la placa de nuevo."""
    consulta = db.query(Acceso).filter(Acceso.fecha_hora_salida.is_(None))
    if zona_id is not None:
        consulta = consulta.filter(Acceso.zona_id == zona_id)
    accesos = consulta.order_by(Acceso.fecha_hora_entrada).all()

    # El codigo del espacio es un dato de cortesia: si el servicio de parqueadero no responde,
    # el vigilante igual ve los vehiculos y puede registrar salidas.
    try:
        codigos = parqueadero_client.codigos_de_espacios(
            [acceso.espacio_id for acceso in accesos if acceso.espacio_id is not None]
        )
    except ParqueaderoNoDisponibleError:
        codigos = {}

    return [
        AccesoActivoRead(
            **AccesoRead.model_validate(acceso).model_dump(),
            placa=acceso.placa,
            espacio_codigo=codigos.get(acceso.espacio_id),
        )
        for acceso in accesos
    ]


# GET /accesos/buscar?placa= (vigilante, admin): el acceso abierto de una placa, para ofrecer la salida.
@router.get("/buscar", response_model=AccesoRead)
def buscar_acceso_activo(
    placa: str,
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role_token(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    """Usado por el panel de vigilancia para saber si una placa tiene un acceso abierto
    (y por lo tanto corresponde ofrecer 'registrar salida' en vez de una nueva entrada).
    Usa la placa guardada en el acceso, sin leer la tabla de vehiculos."""
    acceso = (
        db.query(Acceso)
        .filter(Acceso.placa == placa.strip().upper(), Acceso.fecha_hora_salida.is_(None))
        .first()
    )
    if acceso is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hay un acceso activo para esa placa")
    return acceso


# POST /accesos/entrada (vigilante, admin): registra una entrada; traduce los errores del service a 404/409/503.
@router.post("/entrada", response_model=AccesoRead, status_code=status.HTTP_201_CREATED)
def registrar_entrada(
    datos: AccesoEntradaCreate,
    db: Session = Depends(get_db),
    vigilante: UsuarioToken = Depends(require_role_token(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    try:
        return acceso_service.registrar_entrada(db, datos, realizado_por_id=vigilante.id)
    except (VehiculoNoEncontradoError, acceso_service.UsuarioNoEncontradoError) as exc:
        raise _entrada_rechazada(status.HTTP_404_NOT_FOUND, exc) from exc
    except (
        acceso_service.ParqueaderoCerradoError,
        acceso_service.VehiculoNoVerificadoError,
        acceso_service.VehiculoYaAdentroError,
    ) as exc:
        raise _entrada_rechazada(status.HTTP_409_CONFLICT, exc) from exc
    except IdentidadNoDisponibleError as exc:
        raise _entrada_rechazada(status.HTTP_503_SERVICE_UNAVAILABLE, exc) from exc
    except CupoNoDisponibleError as exc:
        raise _entrada_rechazada(status.HTTP_409_CONFLICT, exc) from exc
    except ParqueaderoNoDisponibleError as exc:
        raise _entrada_rechazada(status.HTTP_503_SERVICE_UNAVAILABLE, exc) from exc


# Deja en la consola por que se rechazo la entrada y arma la respuesta de error.
def _entrada_rechazada(codigo: int, exc: Exception) -> HTTPException:
    logger.warning("Accesos: entrada rechazada (%s): %s", codigo, exc)
    return HTTPException(status_code=codigo, detail=str(exc))


# POST /accesos/{id}/salida (vigilante, admin): registra la salida y libera el cupo.
@router.post("/{acceso_id}/salida", response_model=AccesoRead)
def registrar_salida(
    acceso_id: uuid.UUID,
    db: Session = Depends(get_db),
    vigilante: UsuarioToken = Depends(require_role_token(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    try:
        return acceso_service.registrar_salida(db, acceso_id, realizado_por_id=vigilante.id)
    except acceso_service.AccesoNoEncontradoOYaCerradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CupoNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ParqueaderoNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
