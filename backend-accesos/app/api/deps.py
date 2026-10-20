import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decodificar_token
from app.db.session import get_db
from app.models.enums import RolUsuario

# Lee el token del encabezado Authorization: Bearer <token>.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

__all__ = ["get_db", "UsuarioToken", "get_usuario_token", "require_role_token"]


# El usuario que hace la peticion, segun su token.
@dataclass(frozen=True)
class UsuarioToken:
    """Lo que accesos sabe del usuario: solo lo que trae el token. No consulta la tabla de
    usuarios, asi sigue funcionando aunque el servicio de identidad este caido."""

    id: uuid.UUID
    rol: RolUsuario


# Valida el token y saca de el el id y el rol (si no sirve, 401).
def get_usuario_token(token: str = Depends(oauth2_scheme)) -> UsuarioToken:
    try:
        payload = decodificar_token(token)
        return UsuarioToken(id=uuid.UUID(payload["sub"]), rol=RolUsuario(payload["rol"]))
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token invalido") from exc


# Deja pasar solo a los roles indicados (si no, 403); se usa en cada endpoint.
def require_role_token(*roles: RolUsuario):
    def verificador(usuario: UsuarioToken = Depends(get_usuario_token)) -> UsuarioToken:
        if usuario.rol not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Rol no autorizado")
        return usuario

    return verificador
