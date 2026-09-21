import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.auditoria_acceso import AuditoriaAcceso
from app.models.enums import AccionAuditoria


def registrar_auditoria(
    db: Session,
    *,
    tabla_afectada: str,
    registro_id: uuid.UUID,
    accion: AccionAuditoria,
    realizado_por_id: uuid.UUID,
    valores_anteriores: dict[str, Any] | None = None,
    valores_nuevos: dict[str, Any] | None = None,
    motivo: str | None = None,
    ip_origen: str | None = None,
) -> AuditoriaAcceso:
    """RN-04: escribe la traza dentro de la misma transaccion que la mutacion de negocio.

    No hace commit: el caller (acceso_service, etc.) controla la transaccion para que la
    mutacion y su traza de auditoria vivan o mueran juntas.
    """
    entrada = AuditoriaAcceso(
        tabla_afectada=tabla_afectada,
        registro_id=registro_id,
        accion=accion,
        valores_anteriores=valores_anteriores,
        valores_nuevos=valores_nuevos,
        realizado_por_id=realizado_por_id,
        motivo=motivo,
        ip_origen=ip_origen,
    )
    db.add(entrada)
    db.flush()
    return entrada
