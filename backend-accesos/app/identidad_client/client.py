# Cliente HTTP para hablar con el servicio de identidad por su API interna (/interno).
import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings


class VehiculoNoEncontradoError(Exception):
    """El servicio de identidad no tiene un vehiculo con ese id."""


class IdentidadNoDisponibleError(Exception):
    """El servicio de identidad no respondio o respondio algo inesperado."""


# Lo que responde identidad sobre un vehiculo.
@dataclass(frozen=True)
class VehiculoIdentidad:
    """Lo que accesos necesita saber de un vehiculo para registrar su entrada."""

    id: uuid.UUID
    placa: str
    es_visitante: bool
    estado_verificacion: str
    # None cuando el vehiculo no tiene dueno registrado (visitante).
    propietario_id: uuid.UUID | None
    propietario_estado_verificacion: str | None
    # False si el dueno fue dado de baja (RN-08).
    propietario_activo: bool | None


# Pide a identidad un vehiculo por su id (si no existe, VehiculoNoEncontradoError).
def obtener_vehiculo(vehiculo_id: uuid.UUID) -> VehiculoIdentidad:
    """Los vehiculos viven en la base de datos del servicio de identidad, asi que se le
    preguntan por API en vez de con una consulta local."""
    respuesta = _pedir(f"/interno/vehiculos/{vehiculo_id}")
    if respuesta.status_code == 404:
        raise VehiculoNoEncontradoError("El vehiculo no existe")
    cuerpo = _json(respuesta)
    try:
        propietario = cuerpo["propietario"]
        return VehiculoIdentidad(
            id=uuid.UUID(cuerpo["id"]),
            placa=str(cuerpo["placa"]),
            es_visitante=bool(cuerpo["es_visitante"]),
            estado_verificacion=str(cuerpo["estado_verificacion"]),
            propietario_id=uuid.UUID(propietario["id"]) if propietario is not None else None,
            propietario_estado_verificacion=(
                str(propietario["estado_verificacion"]) if propietario is not None else None
            ),
            propietario_activo=bool(propietario["activo"]) if propietario is not None else None,
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc


# Pregunta a identidad cuales de esos usuarios existen.
def usuarios_existentes(usuario_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """De los identificadores pedidos, los que corresponden a un usuario que existe."""
    if not usuario_ids:
        return set()
    respuesta = _pedir("/interno/usuarios", params={"id": [str(i) for i in usuario_ids]})
    try:
        return {uuid.UUID(usuario["id"]) for usuario in _json(respuesta)}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc


# Lo que responde identidad sobre un usuario: su rol y si sigue activo.
@dataclass(frozen=True)
class UsuarioIdentidad:
    id: uuid.UUID
    rol: str
    activo: bool


# Pide a identidad un usuario por su id; None si no existe.
def obtener_usuario(usuario_id: uuid.UUID) -> UsuarioIdentidad | None:
    """Lo usa el cierre de semestre para comprobar que quien lo corre es un administrador activo."""
    respuesta = _pedir("/interno/usuarios", params={"id": [str(usuario_id)]})
    try:
        for usuario in _json(respuesta):
            if uuid.UUID(usuario["id"]) == usuario_id:
                return UsuarioIdentidad(
                    id=usuario_id, rol=str(usuario["rol"]), activo=bool(usuario["activo"])
                )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc
    return None


# Hace el GET con 5 s de espera; si identidad no responde, IdentidadNoDisponibleError.
def _pedir(ruta: str, **kwargs) -> httpx.Response:
    try:
        with httpx.Client(base_url=settings.IDENTIDAD_URL, timeout=5.0) as client:
            respuesta = client.get(ruta, **kwargs)
    except httpx.HTTPError as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc

    if respuesta.status_code not in (200, 404):
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible")
    return respuesta


# Lee la respuesta como JSON o falla con IdentidadNoDisponibleError.
def _json(respuesta: httpx.Response):
    if respuesta.status_code != 200:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible")
    try:
        return respuesta.json()
    except ValueError as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc
