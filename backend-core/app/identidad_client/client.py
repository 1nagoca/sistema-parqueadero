import uuid
from dataclasses import dataclass

import httpx

from app.core.config import settings


class VehiculoNoEncontradoError(Exception):
    """El servicio de identidad no tiene un vehiculo con ese id."""


class IdentidadNoDisponibleError(Exception):
    """El servicio de identidad no respondio o respondio algo inesperado."""


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
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc


def usuarios_existentes(usuario_ids: list[uuid.UUID]) -> set[uuid.UUID]:
    """De los identificadores pedidos, los que corresponden a un usuario que existe."""
    if not usuario_ids:
        return set()
    respuesta = _pedir("/interno/usuarios", params={"id": [str(i) for i in usuario_ids]})
    try:
        return {uuid.UUID(usuario["id"]) for usuario in _json(respuesta)}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc


def _pedir(ruta: str, **kwargs) -> httpx.Response:
    try:
        with httpx.Client(base_url=settings.IDENTIDAD_URL, timeout=5.0) as client:
            respuesta = client.get(ruta, **kwargs)
    except httpx.HTTPError as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc

    if respuesta.status_code not in (200, 404):
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible")
    return respuesta


def _json(respuesta: httpx.Response):
    if respuesta.status_code != 200:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible")
    try:
        return respuesta.json()
    except ValueError as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc
