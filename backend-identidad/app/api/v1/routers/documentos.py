import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.documento import Documento
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.services import documento_service

router = APIRouter(prefix="/documentos", tags=["documentos"])


@router.get("/{documento_id}/archivo")
def descargar_documento(
    documento_id: uuid.UUID,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
) -> FileResponse:
    """Solo el administrador y el dueno del documento pueden verlo (son datos personales
    sensibles, por eso no se sirven como archivos estaticos)."""
    documento = db.get(Documento, documento_id)
    if documento is None or (usuario.rol != RolUsuario.ADMIN and documento.usuario_id != usuario.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado")
    try:
        ruta = documento_service.ruta_absoluta(documento.ruta_archivo)
    except documento_service.ArchivoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento no encontrado") from exc
    if not ruta.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Archivo no disponible")
    return FileResponse(
        ruta,
        media_type=documento.content_type,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
