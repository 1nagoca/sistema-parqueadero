import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.documento import Documento
from app.models.enums import EstadoVerificacion, RolUsuario, TipoDocumento
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.auditoria_identidad import AuditoriaIdentidadPagina, AuditoriaIdentidadRead
from app.schemas.documento import (
    ResolverVerificacion,
    SolicitudVerificacion,
    UsuarioConDocumentos,
    VehiculoConDocumentos,
)
from app.schemas.usuario import UsuarioRead
from app.schemas.vehiculo import VehiculoRead
from app.services import auditoria_service, verificacion_service

router = APIRouter(prefix="/verificaciones", tags=["verificaciones"])


# GET /verificaciones/pendientes (admin): bandeja de estudiantes y vehiculos por revisar.
@router.get("/pendientes", response_model=list[SolicitudVerificacion])
def listar_pendientes(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    """Bandeja del administrador: estudiantes con el carnet por revisar y/o vehiculos
    pendientes. Un estudiante que se registro pero aun no sube nada no aparece, ni uno dado de baja."""
    con_carnet = (
        db.query(Documento.usuario_id).filter(Documento.tipo == TipoDocumento.CARNET).scalar_subquery()
    )
    con_vehiculo_pendiente = (
        db.query(Vehiculo.usuario_id)
        .filter(Vehiculo.estado_verificacion == EstadoVerificacion.PENDIENTE, Vehiculo.usuario_id.is_not(None))
        .scalar_subquery()
    )
    usuarios = (
        db.query(Usuario)
        .filter(
            Usuario.activo.is_(True),
            or_(
                (Usuario.estado_verificacion == EstadoVerificacion.PENDIENTE) & Usuario.id.in_(con_carnet),
                Usuario.id.in_(con_vehiculo_pendiente),
            ),
        )
        .order_by(Usuario.creado_en)
        .all()
    )

    solicitudes = []
    for usuario in usuarios:
        vehiculos = [
            _con_documentos_vehiculo(v)
            for v in usuario.vehiculos
            if v.estado_verificacion == EstadoVerificacion.PENDIENTE
        ]
        solicitudes.append(
            SolicitudVerificacion(usuario=_con_documentos_usuario(usuario), vehiculos=vehiculos)
        )
    return solicitudes


# POST /verificaciones/usuarios/{id}/resolver (admin): aprueba o rechaza a un estudiante.
@router.post("/usuarios/{usuario_id}/resolver", response_model=UsuarioRead)
def resolver_usuario(
    usuario_id: uuid.UUID,
    datos: ResolverVerificacion,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or usuario.rol != RolUsuario.ESTUDIANTE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estudiante no encontrado")
    try:
        return verificacion_service.resolver_usuario(db, usuario, datos.aprobar, datos.motivo, admin.id)
    except verificacion_service.VerificacionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# POST /verificaciones/vehiculos/{id}/resolver (admin): aprueba o rechaza un vehiculo.
@router.post("/vehiculos/{vehiculo_id}/resolver", response_model=VehiculoRead)
def resolver_vehiculo(
    vehiculo_id: uuid.UUID,
    datos: ResolverVerificacion,
    db: Session = Depends(get_db),
    admin: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    vehiculo = db.get(Vehiculo, vehiculo_id)
    if vehiculo is None or vehiculo.usuario_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")
    try:
        return verificacion_service.resolver_vehiculo(db, vehiculo, datos.aprobar, datos.motivo, admin.id)
    except verificacion_service.VerificacionError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


# GET /verificaciones/auditoria (admin): trazas de verificaciones entre dos fechas (por defecto el semestre actual), paginadas.
@router.get("/auditoria", response_model=AuditoriaIdentidadPagina)
def listar_auditoria(
    desde: date | None = None,
    hasta: date | None = None,
    tabla_afectada: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
) -> AuditoriaIdentidadPagina:
    """Solo lectura: la tabla es append-only, no existen endpoints de escritura directa (las
    trazas las genera exclusivamente el servicio de verificacion)."""
    try:
        desde, hasta = auditoria_service.resolver_rango(desde, hasta)
    except auditoria_service.RangoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    items, total = auditoria_service.listar_auditoria(
        db, desde=desde, hasta=hasta, tabla_afectada=tabla_afectada, pagina=pagina, por_pagina=por_pagina
    )
    return AuditoriaIdentidadPagina(
        items=[AuditoriaIdentidadRead.model_validate(t) for t in items],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        desde=desde,
        hasta=hasta,
    )


# Arma la respuesta del estudiante solo con su carnet.
def _con_documentos_usuario(usuario: Usuario) -> UsuarioConDocumentos:
    base = UsuarioConDocumentos.model_validate(usuario)
    return base.model_copy(update={"documentos": [d for d in base.documentos if d.tipo == TipoDocumento.CARNET]})


# Arma la respuesta del vehiculo con sus documentos.
def _con_documentos_vehiculo(vehiculo: Vehiculo) -> VehiculoConDocumentos:
    return VehiculoConDocumentos.model_validate(vehiculo)
