import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import decodificar_token
from app.db.session import get_db
from app.models.enums import RolUsuario
from app.models.usuario import Usuario

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

__all__ = [
    "get_db",
    "get_current_user",
    "require_role",
    "UsuarioToken",
    "get_usuario_token",
    "require_role_token",
]


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

    usuario = db.get(Usuario, uuid.UUID(usuario_id))
    if usuario is None or not usuario.activo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo o inexistente")
    return usuario


def require_role(*roles: RolUsuario):
    def verificador(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.rol not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return usuario

    return verificador


@dataclass(frozen=True)
class UsuarioToken:
    """Lo que accesos sabe del usuario: solo lo que trae el token. No consulta la tabla de
    usuarios, asi sigue funcionando aunque el servicio de identidad este caido."""

    id: uuid.UUID
    rol: RolUsuario


def get_usuario_token(token: str = Depends(oauth2_scheme)) -> UsuarioToken:
    try:
        payload = decodificar_token(token)
        return UsuarioToken(id=uuid.UUID(payload["sub"]), rol=RolUsuario(payload["rol"]))
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido") from exc


def require_role_token(*roles: RolUsuario):
    def verificador(usuario: UsuarioToken = Depends(get_usuario_token)) -> UsuarioToken:
        if usuario.rol not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return usuario

    return verificador
