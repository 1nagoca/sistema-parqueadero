import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_token
from app.db.session import get_db
from app.models.enums import RolUsuario
from app.models.usuario import Usuario

# Lee el token del encabezado Authorization: Bearer <token>.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

__all__ = ["get_db", "get_current_user", "require_role"]


# Valida el token y busca al usuario en la base; si no existe o esta inactivo, 401.
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    try:
        payload = decodificar_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido") from exc

    usuario_id = payload.get("sub")
    if usuario_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido")

    try:
        usuario_uuid = uuid.UUID(usuario_id)
    except (ValueError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido") from exc

    usuario = db.get(Usuario, usuario_uuid)
    if usuario is None or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o inexistente")
    return usuario


# Deja pasar solo a los roles indicados (si no, 403); se usa en cada endpoint.
def require_role(*roles: RolUsuario):
    def verificador(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return usuario

    return verificador
