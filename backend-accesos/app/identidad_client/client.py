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
    # None si es una moto electrica: va por su numero de serie.
    placa: str | None
    es_visitante: bool
    estado_verificacion: str
    # None cuando el vehiculo no tiene dueno registrado (visitante).
    propietario_id: uuid.UUID | None
    propietario_estado_verificacion: str | None
    # False si el dueno fue dado de baja (RN-08).
    propietario_activo: bool | None
    # Moto electrica sin placa; una identidad sin estos campos se lee como moto con placa.
    es_electrica: bool = False
    numero_serie: str | None = None


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
        placa = cuerpo["placa"]
        es_electrica = bool(cuerpo.get("es_electrica", False))
        numero_serie = cuerpo.get("numero_serie")
        # placa o serial segun el tipo; si no cuadran (el CHECK de accesos fallaria), es una respuesta inesperada
        if (placa is None) != es_electrica or (numero_serie is None) == es_electrica:
            raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible")
        return VehiculoIdentidad(
            id=uuid.UUID(cuerpo["id"]),
            placa=None if placa is None else str(placa),
            es_visitante=bool(cuerpo["es_visitante"]),
            estado_verificacion=str(cuerpo["estado_verificacion"]),
            propietario_id=uuid.UUID(propietario["id"]) if propietario is not None else None,
            propietario_estado_verificacion=(
                str(propietario["estado_verificacion"]) if propietario is not None else None
            ),
            propietario_activo=bool(propietario["activo"]) if propietario is not None else None,
            es_electrica=es_electrica,
            numero_serie=None if numero_serie is None else str(numero_serie),
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
    """Lo usan el cierre de semestre, para comprobar que quien lo corre es un administrador activo,
    y la entrada, para validar a quien la autoriza."""
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


# Pregunta a identidad los ids de los vehiculos de un usuario ([] si no tiene).
def vehiculos_de_usuario(usuario_id: uuid.UUID) -> list[uuid.UUID]:
    """Lo usa GET /accesos/mio: Acceso.usuario_id es el conductor y casi siempre va vacio,
    asi que la moto del estudiante se reconoce por sus vehiculos en identidad."""
    respuesta = _pedir(f"/interno/usuarios/{usuario_id}/vehiculos")
    cuerpo = _json(respuesta)
    if not isinstance(cuerpo, list):
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible")
    try:
        return [uuid.UUID(vehiculo_id) for vehiculo_id in cuerpo]
    except (TypeError, ValueError, AttributeError) as exc:
        raise IdentidadNoDisponibleError("El servicio de identidad no esta disponible") from exc


# Hace el GET con 5 s de espera; si identidad no responde, IdentidadNoDisponibleError.
def _pedir(ruta: str, **kwargs) -> httpx.Response:
    try:
        # la clave interna va en cada llamada; identidad y parqueadero responden 401 sin ella
        with httpx.Client(
            base_url=settings.IDENTIDAD_URL, timeout=5.0, headers={"X-Clave-Interna": settings.CLAVE_INTERNA}
        ) as client:
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
