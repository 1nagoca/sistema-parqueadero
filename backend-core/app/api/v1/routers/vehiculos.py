import re
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.enums import EstadoVerificacion, RolUsuario, TipoDocumento, TipoVehiculo
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.documento import VehiculoConDocumentos
from app.schemas.vehiculo import VehiculoCreate, VehiculoRead
from app.services import documento_service, vehiculo_service, verificacion_service

router = APIRouter(prefix="/vehiculos", tags=["vehiculos"])

# Formatos de placa colombianos: carro ABC123; moto ABC12 o ABC12D.
_PLACA_POR_TIPO = {
    TipoVehiculo.CARRO: re.compile(r"^[A-Z]{3}\d{3}$"),
    TipoVehiculo.MOTO: re.compile(r"^[A-Z]{3}\d{2}[A-Z]?$"),
}


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


@router.get("/mis-vehiculos", response_model=list[VehiculoConDocumentos])
def listar_mis_vehiculos(
    db: Session = Depends(get_db),
    estudiante: Usuario = Depends(require_role(RolUsuario.ESTUDIANTE)),
):
    return (
        db.query(Vehiculo).filter(Vehiculo.usuario_id == estudiante.id).order_by(Vehiculo.creado_en.desc()).all()
    )


@router.post("/mis-vehiculos", response_model=VehiculoConDocumentos, status_code=status.HTTP_201_CREATED)
async def registrar_mi_vehiculo(
    placa: str = Form(...),
    tipo_vehiculo: TipoVehiculo = Form(...),
    marca: str | None = Form(None, max_length=50),
    modelo: str | None = Form(None, max_length=50),
    color: str | None = Form(None, max_length=30),
    foto_placa: UploadFile = File(...),
    tarjeta_propiedad: UploadFile = File(...),
    db: Session = Depends(get_db),
    estudiante: Usuario = Depends(require_role(RolUsuario.ESTUDIANTE)),
):
    """El propio estudiante registra su vehiculo con la foto de la placa y la tarjeta de
    propiedad. Queda ``pendiente`` hasta que el administrador lo apruebe."""
    placa = placa.strip().upper()
    patron = _PLACA_POR_TIPO.get(tipo_vehiculo)
    if patron is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Solo se registran carros o motos"
        )
    if not patron.match(placa):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"La placa {placa} no tiene un formato valido para {tipo_vehiculo.value}",
        )
    if vehiculo_service.obtener_por_placa(db, placa) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La placa ya esta registrada")

    archivos = await _guardar_documentos_vehiculo(foto_placa, tarjeta_propiedad)
    vehiculo = Vehiculo(
        placa=placa,
        tipo_vehiculo=tipo_vehiculo,
        marca=marca,
        modelo=modelo,
        color=color,
        usuario_id=estudiante.id,
        estado_verificacion=EstadoVerificacion.PENDIENTE,
    )
    try:
        db.add(vehiculo)
        db.flush()
        for tipo, (ruta, content_type, tamano) in archivos.items():
            verificacion_service.reemplazar_documento(
                db,
                usuario_id=estudiante.id,
                vehiculo_id=vehiculo.id,
                tipo=tipo,
                ruta=ruta,
                content_type=content_type,
                tamano=tamano,
            )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        verificacion_service.borrar_archivos([ruta for ruta, _, _ in archivos.values()])
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La placa ya esta registrada") from exc
    except Exception:
        db.rollback()
        verificacion_service.borrar_archivos([ruta for ruta, _, _ in archivos.values()])
        raise
    db.refresh(vehiculo)
    return vehiculo


@router.post("/mis-vehiculos/{vehiculo_id}/reenviar", response_model=VehiculoConDocumentos)
async def reenviar_documentos_vehiculo(
    vehiculo_id: uuid.UUID,
    foto_placa: UploadFile = File(...),
    tarjeta_propiedad: UploadFile = File(...),
    db: Session = Depends(get_db),
    estudiante: Usuario = Depends(require_role(RolUsuario.ESTUDIANTE)),
):
    """Corregir y reenviar los documentos de un vehiculo rechazado."""
    vehiculo = db.get(Vehiculo, vehiculo_id)
    if vehiculo is None or vehiculo.usuario_id != estudiante.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")
    if vehiculo.estado_verificacion != EstadoVerificacion.RECHAZADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Solo se pueden reenviar documentos de un vehiculo rechazado"
        )

    archivos = await _guardar_documentos_vehiculo(foto_placa, tarjeta_propiedad)
    viejas: list[str] = []
    try:
        for tipo, (ruta, content_type, tamano) in archivos.items():
            viejas += verificacion_service.reemplazar_documento(
                db,
                usuario_id=estudiante.id,
                vehiculo_id=vehiculo.id,
                tipo=tipo,
                ruta=ruta,
                content_type=content_type,
                tamano=tamano,
            )
        vehiculo.estado_verificacion = EstadoVerificacion.PENDIENTE
        vehiculo.motivo_rechazo = None
        db.commit()
    except Exception:
        db.rollback()
        verificacion_service.borrar_archivos([ruta for ruta, _, _ in archivos.values()])
        raise
    verificacion_service.borrar_archivos(viejas)
    db.refresh(vehiculo)
    return vehiculo


async def _guardar_documentos_vehiculo(
    foto_placa: UploadFile, tarjeta_propiedad: UploadFile
) -> dict[TipoDocumento, tuple[str, str, int]]:
    """Guarda ambos archivos; si el segundo es invalido, borra el primero para no dejar basura."""
    guardados: dict[TipoDocumento, tuple[str, str, int]] = {}
    try:
        guardados[TipoDocumento.FOTO_PLACA] = await documento_service.guardar_archivo(
            foto_placa, permitir_pdf=False
        )
        guardados[TipoDocumento.TARJETA_PROPIEDAD] = await documento_service.guardar_archivo(tarjeta_propiedad)
    except documento_service.ArchivoInvalidoError as exc:
        verificacion_service.borrar_archivos([ruta for ruta, _, _ in guardados.values()])
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return guardados
