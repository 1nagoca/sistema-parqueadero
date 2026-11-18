import logging
import uuid
from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decodificar_token
from app.db.session import get_db
from app.identidad_client import client as identidad_client
from app.models.enums import RolUsuario

# Lee el token del encabezado Authorization: Bearer <token>.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
logger = logging.getLogger(__name__)

__all__ = ["get_db", "UsuarioToken", "get_usuario_token", "require_role_token", "require_rol_activo"]


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


# Como require_role_token y ademas pide a identidad que el usuario siga activo (si no, 401); si identidad no responde, deja pasar.
def require_rol_activo(*roles: RolUsuario):
    verificar_rol = require_role_token(*roles)

    def verificador(usuario: UsuarioToken = Depends(verificar_rol)) -> UsuarioToken:
        try:
            en_identidad = identidad_client.obtener_usuario(usuario.id)
        except identidad_client.IdentidadNoDisponibleError:
            logger.warning("Accesos: identidad no responde; no se comprobo si el usuario %s sigue activo", usuario.id)
            return usuario
        if en_identidad is None or not en_identidad.activo:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario inactivo")
        return usuario

    return verificador
