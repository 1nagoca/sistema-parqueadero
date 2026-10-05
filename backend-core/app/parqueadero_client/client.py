import uuid

import httpx

from app.core.config import settings


class CupoNoDisponibleError(Exception):
    """El servicio de parqueadero rechazo la operacion: zona sin cupos, espacio no libre o
    zona ya en su capacidad total (RN-01 / RN-02)."""


class ParqueaderoNoDisponibleError(Exception):
    """El servicio de parqueadero no respondio o respondio con un error inesperado."""


def ocupar_cupo(zona_id: uuid.UUID, espacio_id: uuid.UUID | None) -> None:
    _mover_cupo("ocupar", zona_id, espacio_id)


def liberar_cupo(zona_id: uuid.UUID, espacio_id: uuid.UUID | None) -> None:
    _mover_cupo("liberar", zona_id, espacio_id)


def codigos_de_espacios(espacio_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Codigo visible de cada espacio (ej. "A-12"). Los espacios viven en la base de datos del
    servicio de parqueadero, asi que se le preguntan por API en vez de con un JOIN."""
    if not espacio_ids:
        return {}
    respuesta = _pedir("GET", "/interno/espacios", params={"id": [str(i) for i in espacio_ids]})
    return {uuid.UUID(espacio["id"]): espacio["codigo"] for espacio in respuesta.json()}


def _mover_cupo(accion: str, zona_id: uuid.UUID, espacio_id: uuid.UUID | None) -> None:
    _pedir(
        "POST",
        f"/interno/cupos/{accion}",
        json={"zona_id": str(zona_id), "espacio_id": str(espacio_id) if espacio_id else None},
    )


def _pedir(metodo: str, ruta: str, **kwargs) -> httpx.Response:
    try:
        with httpx.Client(base_url=settings.PARQUEADERO_URL, timeout=5.0) as client:
            respuesta = client.request(metodo, ruta, **kwargs)
    except httpx.HTTPError as exc:
        raise ParqueaderoNoDisponibleError("El servicio de parqueadero no esta disponible") from exc

    if respuesta.status_code == 409:
        raise CupoNoDisponibleError(respuesta.json().get("detail", "Cupo no disponible"))
    if respuesta.status_code != 200:
        raise ParqueaderoNoDisponibleError(
            f"El servicio de parqueadero respondio {respuesta.status_code}"
        )
    return respuesta
