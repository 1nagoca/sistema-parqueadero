from typing import Any

from jose import JWTError, jwt

from app.core.config import settings


# Verifica la firma y la expiracion del token y devuelve su contenido.
def decodificar_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Token invalido o expirado") from exc
