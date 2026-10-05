import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.acceso import Acceso
from app.models.enums import EstadoVerificacion, RolUsuario, TipoAcceso
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.acceso import AccesoActivoRead, AccesoEntradaCreate, AccesoRead
from app.parqueadero_client import client as parqueadero_client
from app.parqueadero_client.client import CupoNoDisponibleError, ParqueaderoNoDisponibleError
from app.services import acceso_service, vehiculo_service

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
        db.query(Acceso, Vehiculo.placa)
        .join(Vehiculo, Vehiculo.id == Acceso.vehiculo_id)
        .filter(Acceso.fecha_hora_salida.is_(None))
    )
    if zona_id is not None:
        consulta = consulta.filter(Acceso.zona_id == zona_id)
    filas = consulta.order_by(Acceso.fecha_hora_entrada).all()

    # El codigo del espacio es un dato de cortesia: si el servicio de parqueadero no responde,
    # el vigilante igual ve los vehiculos y puede registrar salidas.
    try:
        codigos = parqueadero_client.codigos_de_espacios(
            [acceso.espacio_id for acceso, _ in filas if acceso.espacio_id is not None]
        )
    except ParqueaderoNoDisponibleError:
        codigos = {}

    return [
        AccesoActivoRead(
            **AccesoRead.model_validate(acceso).model_dump(),
            placa=placa,
            espacio_codigo=codigos.get(acceso.espacio_id),
        )
        for acceso, placa in filas
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
    db: Session = Depends(get_db),
    vigilante: Usuario = Depends(require_role(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    _exigir_vehiculo_verificado(db, datos)
    try:
        return acceso_service.registrar_entrada(db, datos, realizado_por_id=vigilante.id)
    except CupoNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ParqueaderoNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


def _exigir_vehiculo_verificado(db: Session, datos: AccesoEntradaCreate) -> None:
    """Un acceso normal exige vehiculo y propietario aprobados por el administrador; el
    visitante ya pasa por su propio flujo de autorizacion + justificacion."""
    if datos.tipo_acceso != TipoAcceso.NORMAL:
        return
    vehiculo = db.get(Vehiculo, datos.vehiculo_id)
    if vehiculo is None:
        return
    propietario = db.get(Usuario, vehiculo.usuario_id) if vehiculo.usuario_id is not None else None
    if vehiculo.estado_verificacion != EstadoVerificacion.APROBADO or (
        propietario is not None and propietario.estado_verificacion != EstadoVerificacion.APROBADO
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El vehiculo o su propietario aun no estan verificados por el administrador",
        )


@router.post("/{acceso_id}/salida", response_model=AccesoRead)
def registrar_salida(
    acceso_id: uuid.UUID,
    db: Session = Depends(get_db),
    vigilante: Usuario = Depends(require_role(RolUsuario.VIGILANTE, RolUsuario.ADMIN)),
):
    try:
        return acceso_service.registrar_salida(db, acceso_id, realizado_por_id=vigilante.id)
    except acceso_service.AccesoNoEncontradoOYaCerradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except CupoNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ParqueaderoNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
