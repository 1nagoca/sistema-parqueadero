import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.documento import Documento
from app.models.enums import AccionAuditoria, EstadoVerificacion, RolUsuario
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.services import auditoria_service, verificacion_service

# Roles que el administrador puede dar de baja o reactivar (RN-08).
ROLES_CON_BAJA = (RolUsuario.ESTUDIANTE, RolUsuario.VIGILANTE)

MOTIVO_REACTIVACION = "Cuenta reactivada por el administrador"
MOTIVO_VEHICULO_REACTIVADO = (
    "Cuenta reactivada: vuelve a subir la foto de la placa y la tarjeta de propiedad"
)


class UsuarioNoEncontradoError(Exception):
    """No existe un usuario con ese id."""


class UsuarioConflictoError(Exception):
    """La baja o la reactivacion no aplica (propia cuenta, rol o estado actual)."""


# Una pagina de usuarios con filtros; el conteo y el corte se hacen en SQL.
def listar_usuarios(
    db: Session,
    *,
    pagina: int,
    por_pagina: int,
    buscar: str | None = None,
    rol: RolUsuario | None = None,
    activo: bool | None = None,
) -> tuple[list[Usuario], int]:
    consulta = db.query(Usuario)
    texto = (buscar or "").strip()
    if texto:
        # Escapa % y _ para que se busquen tal cual.
        patron = "%" + texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        consulta = consulta.filter(
            or_(
                Usuario.nombre_completo.ilike(patron, escape="\\"),
                Usuario.correo_institucional.ilike(patron, escape="\\"),
                Usuario.documento_identidad.ilike(patron, escape="\\"),
            )
        )
    if rol is not None:
        consulta = consulta.filter(Usuario.rol == rol)
    if activo is not None:
        consulta = consulta.filter(Usuario.activo.is_(activo))

    total = consulta.count()
    items = (
        consulta.order_by(Usuario.nombre_completo, Usuario.id)
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )
    return items, total


# Da de baja al usuario, borra sus documentos y deja la traza con el motivo.
def dar_de_baja(db: Session, usuario_id: uuid.UUID, motivo: str, admin_id: uuid.UUID) -> Usuario:
    """Los vehiculos y los accesos se conservan (RN-03); los archivos se borran del disco
    despues del commit, para no perderlos si la transaccion falla."""
    usuario = _bloquear_para_cambio(db, usuario_id, admin_id)
    if not usuario.activo:
        raise UsuarioConflictoError("El usuario ya esta dado de baja")

    # Documentos del usuario (carnet) y de sus vehiculos (foto de placa y tarjeta).
    sus_vehiculos = select(Vehiculo.id).where(Vehiculo.usuario_id == usuario.id)
    documentos = (
        db.query(Documento)
        .filter(or_(Documento.usuario_id == usuario.id, Documento.vehiculo_id.in_(sus_vehiculos)))
        .all()
    )
    rutas = [d.ruta_archivo for d in documentos]
    for documento in documentos:
        db.delete(documento)

    usuario.activo = False
    auditoria_service.registrar_auditoria(
        db,
        tabla_afectada="usuarios",
        registro_id=usuario.id,
        accion=AccionAuditoria.ACTUALIZACION,
        realizado_por_id=admin_id,
        valores_anteriores={"activo": True},
        valores_nuevos={"activo": False},
        motivo=motivo,
    )
    db.commit()
    verificacion_service.borrar_archivos(rutas)
    db.refresh(usuario)
    return usuario


# Reactiva al usuario; el estudiante vuelve a pendiente y sus vehiculos a rechazado.
def reactivar(db: Session, usuario_id: uuid.UUID, admin_id: uuid.UUID) -> Usuario:
    """Como la baja borro los documentos, el estudiante debe subir de nuevo el carnet y reenviar
    los de cada vehiculo (el reenvio solo acepta vehiculos rechazados)."""
    usuario = _bloquear_para_cambio(db, usuario_id, admin_id)
    if usuario.activo:
        raise UsuarioConflictoError("El usuario ya esta activo")

    anteriores: dict[str, object] = {"activo": False}
    nuevos: dict[str, object] = {"activo": True}
    usuario.activo = True
    if usuario.rol == RolUsuario.ESTUDIANTE:
        anteriores["estado_verificacion"] = usuario.estado_verificacion.value
        usuario.estado_verificacion = EstadoVerificacion.PENDIENTE
        usuario.motivo_rechazo = None
        nuevos["estado_verificacion"] = EstadoVerificacion.PENDIENTE.value
        # Cada vehiculo que pasa a rechazado deja su propia traza.
        for vehiculo in usuario.vehiculos:
            estado_anterior = vehiculo.estado_verificacion.value
            vehiculo.estado_verificacion = EstadoVerificacion.RECHAZADO
            vehiculo.motivo_rechazo = MOTIVO_VEHICULO_REACTIVADO
            auditoria_service.registrar_auditoria(
                db,
                tabla_afectada="vehiculos",
                registro_id=vehiculo.id,
                accion=AccionAuditoria.ACTUALIZACION,
                realizado_por_id=admin_id,
                valores_anteriores={"estado_verificacion": estado_anterior},
                valores_nuevos={"estado_verificacion": EstadoVerificacion.RECHAZADO.value},
                motivo=MOTIVO_VEHICULO_REACTIVADO,
            )

    auditoria_service.registrar_auditoria(
        db,
        tabla_afectada="usuarios",
        registro_id=usuario.id,
        accion=AccionAuditoria.ACTUALIZACION,
        realizado_por_id=admin_id,
        valores_anteriores=anteriores,
        valores_nuevos=nuevos,
        motivo=MOTIVO_REACTIVACION,
    )
    db.commit()
    db.refresh(usuario)
    return usuario


# Lee el usuario bloqueando su fila y valida que se le pueda cambiar el estado.
def _bloquear_para_cambio(db: Session, usuario_id: uuid.UUID, admin_id: uuid.UUID) -> Usuario:
    """El bloqueo evita que dos clics seguidos dejen dos trazas."""
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).with_for_update().first()
    if usuario is None:
        raise UsuarioNoEncontradoError("Usuario no encontrado")
    if usuario.id == admin_id:
        raise UsuarioConflictoError("No puedes darte de baja a ti mismo")
    if usuario.rol not in ROLES_CON_BAJA:
        raise UsuarioConflictoError("Solo se dan de baja o se reactivan estudiantes y vigilantes")
    return usuario
