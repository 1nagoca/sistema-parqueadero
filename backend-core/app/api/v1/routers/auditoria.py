from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.auditoria_acceso import AuditoriaAcceso
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.auditoria_acceso import AuditoriaAccesoRead

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


@router.get("", response_model=list[AuditoriaAccesoRead])
def listar_auditoria(
    tabla_afectada: str | None = None,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    """Solo lectura: RN-04 hace que la tabla sea append-only, no existen endpoints de escritura
    directa (las trazas las genera exclusivamente el servicio de negocio)."""
    consulta = db.query(AuditoriaAcceso).order_by(AuditoriaAcceso.fecha_hora.desc())
    if tabla_afectada is not None:
        consulta = consulta.filter(AuditoriaAcceso.tabla_afectada == tabla_afectada)
    return consulta.limit(200).all()
