import uuid

from sqlalchemy.orm import Session

from app.models.documento import Documento
from app.models.enums import AccionAuditoria, EstadoVerificacion, TipoDocumento
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.services import auditoria_service, documento_service


class VerificacionError(Exception):
    """La resolucion no se puede aplicar (faltan documentos o falta el motivo de rechazo)."""


def reemplazar_documento(
    db: Session,
    *,
    usuario_id: uuid.UUID,
    vehiculo_id: uuid.UUID | None,
    tipo: TipoDocumento,
    ruta: str,
    content_type: str,
    tamano: int,
) -> list[str]:
    """Crea el documento y retira el anterior del mismo tipo. Devuelve las rutas de archivos
    viejos para borrarlas del disco *despues* del commit."""
    anteriores = (
        db.query(Documento)
        .filter(Documento.usuario_id == usuario_id, Documento.tipo == tipo, Documento.vehiculo_id == vehiculo_id)
        .all()
    )
    rutas_viejas = [d.ruta_archivo for d in anteriores]
    for doc in anteriores:
        db.delete(doc)
    db.add(
        Documento(
            usuario_id=usuario_id,
            vehiculo_id=vehiculo_id,
            tipo=tipo,
            ruta_archivo=ruta,
            content_type=content_type,
            tamano_bytes=tamano,
        )
    )
    return rutas_viejas


def borrar_archivos(rutas: list[str]) -> None:
    for ruta in rutas:
        documento_service.eliminar_archivo(ruta)


def _tipos_de(documentos: list[Documento]) -> set[TipoDocumento]:
    return {d.tipo for d in documentos}


def resolver_usuario(
    db: Session, usuario: Usuario, aprobar: bool, motivo: str | None, admin_id: uuid.UUID
) -> Usuario:
    if aprobar and TipoDocumento.CARNET not in _tipos_de(usuario.documentos):
        raise VerificacionError("El estudiante aun no ha subido su carnet o captura de Divisist")
    return _aplicar(db, usuario, "usuarios", aprobar, motivo, admin_id)


def resolver_vehiculo(
    db: Session, vehiculo: Vehiculo, aprobar: bool, motivo: str | None, admin_id: uuid.UUID
) -> Vehiculo:
    requeridos = {TipoDocumento.FOTO_PLACA, TipoDocumento.TARJETA_PROPIEDAD}
    if aprobar and not requeridos <= _tipos_de(vehiculo.documentos):
        raise VerificacionError("Faltan la foto de la placa o la tarjeta de propiedad")
    return _aplicar(db, vehiculo, "vehiculos", aprobar, motivo, admin_id)


def _aplicar(db: Session, entidad, tabla: str, aprobar: bool, motivo: str | None, admin_id: uuid.UUID):
    motivo = (motivo or "").strip() or None
    if not aprobar and motivo is None:
        raise VerificacionError("Indica el motivo del rechazo para que el estudiante pueda corregirlo")

    anterior = entidad.estado_verificacion
    entidad.estado_verificacion = EstadoVerificacion.APROBADO if aprobar else EstadoVerificacion.RECHAZADO
    entidad.motivo_rechazo = None if aprobar else motivo

    auditoria_service.registrar_auditoria(
        db,
        tabla_afectada=tabla,
        registro_id=entidad.id,
        accion=AccionAuditoria.ACTUALIZACION,
        realizado_por_id=admin_id,
        valores_anteriores={"estado_verificacion": anterior.value},
        valores_nuevos={"estado_verificacion": entidad.estado_verificacion.value},
        motivo=motivo,
    )
    db.commit()
    db.refresh(entidad)
    return entidad
