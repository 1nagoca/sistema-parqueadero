from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import UsuarioToken, get_db, require_role_token
from app.models.enums import RolUsuario
from app.schemas.auditoria_acceso import AuditoriaAccesoPagina, AuditoriaAccesoRead
from app.services import auditoria_service

router = APIRouter(prefix="/auditoria", tags=["auditoria"])


# GET /auditoria (admin): trazas de entradas y salidas entre dos fechas (por defecto el semestre actual), paginadas.
@router.get("", response_model=AuditoriaAccesoPagina)
def listar_auditoria(
    desde: date | None = None,
    hasta: date | None = None,
    tabla_afectada: str | None = None,
    pagina: int = Query(1, ge=1),
    por_pagina: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role_token(RolUsuario.ADMIN)),
) -> AuditoriaAccesoPagina:
    """Solo lectura: RN-04 hace que la tabla sea append-only, no existen endpoints de escritura
    directa (las trazas las genera exclusivamente el servicio de negocio)."""
    try:
        desde, hasta = auditoria_service.resolver_rango(desde, hasta)
    except auditoria_service.RangoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    items, total = auditoria_service.listar_auditoria(
        db, desde=desde, hasta=hasta, tabla_afectada=tabla_afectada, pagina=pagina, por_pagina=por_pagina
    )
    return AuditoriaAccesoPagina(
        items=[AuditoriaAccesoRead.model_validate(t) for t in items],
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        desde=desde,
        hasta=hasta,
    )
