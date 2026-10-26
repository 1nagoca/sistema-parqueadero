from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

# bcrypt para cifrar contrasenas (nunca se guardan en texto plano).
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hora de Colombia: UTC-5 fijo, sin horario de verano.
COLOMBIA = timezone(timedelta(hours=-5))


# Hora actual en Colombia; unico punto que los tests fijan con monkeypatch.
def ahora_en_colombia() -> datetime:
    return datetime.now(COLOMBIA)


# Abierto de HORARIO_APERTURA a HORARIO_CIERRE (el cierre ya cuenta como cerrado).
def parqueadero_abierto(ahora: datetime) -> bool:
    if not settings.HORARIO_RESTRINGIDO:
        return True
    return settings.HORARIO_APERTURA <= ahora.astimezone(COLOMBIA).time() < settings.HORARIO_CIERRE


# Hora de cierre del mismo dia de `ahora`, en hora de Colombia.
def cierre_de_hoy(ahora: datetime) -> datetime:
    return datetime.combine(ahora.astimezone(COLOMBIA).date(), settings.HORARIO_CIERRE, tzinfo=COLOMBIA)


# Cifra una contrasena para guardarla.
def hashear_password(password: str) -> str:
    return pwd_context.hash(password)


# Compara una contrasena con su version cifrada.
def verificar_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


# Crea el token JWT con el id y el rol del usuario, firmado con SECRET_KEY.
def crear_access_token(
    subject: str, rol: str, expires_delta: timedelta | None = None, expira_en: datetime | None = None
) -> str:
    """El rol viaja en el token para que los demas microservicios autoricen sin consultar la
    base de datos de usuarios."""
    expira = expira_en or datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload: dict[str, Any] = {"sub": subject, "rol": rol, "exp": expira}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


# Verifica la firma y la expiracion del token y devuelve su contenido.
def decodificar_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError as exc:
        raise ValueError("Token invalido o expirado") from exc
