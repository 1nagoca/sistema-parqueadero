"""Cliente del servicio de identidad: como traduce cada respuesta de su API interna (contrato
en docs/arquitectura.md). No llama al servicio real: las respuestas se simulan."""

import os
import uuid

import httpx
import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.core.config import settings  # noqa: E402
from app.identidad_client import client as identidad_client  # noqa: E402

VEHICULO_ID = uuid.uuid4()
PROPIETARIO_ID = uuid.uuid4()
# Se guarda antes de sustituirlo, para poder instalar mas de una respuesta en un mismo test.
CLIENTE_REAL = httpx.Client


@pytest.fixture
def identidad_responde(monkeypatch):
    """Hace que el cliente reciba lo que devuelva ``manejador`` en vez de salir a la red.
    Devuelve la lista de peticiones que se le hicieron."""

    def instalar(manejador):
        peticiones = []

        def transporte(peticion):
            peticiones.append(peticion)
            return manejador(peticion)

        monkeypatch.setattr(
            identidad_client.httpx,
            "Client",
            lambda **kwargs: CLIENTE_REAL(transport=httpx.MockTransport(transporte), **kwargs),
        )
        return peticiones

    return instalar


def _vehiculo(propietario):
    return {
        "id": str(VEHICULO_ID),
        "placa": "ABC123",
        "es_visitante": propietario is None,
        "estado_verificacion": "aprobado",
        "propietario": propietario,
    }


def test_obtener_vehiculo_con_y_sin_propietario(identidad_responde):
    propietario = {"id": str(PROPIETARIO_ID), "estado_verificacion": "pendiente"}
    peticiones = identidad_responde(lambda peticion: httpx.Response(200, json=_vehiculo(propietario)))

    vehiculo = identidad_client.obtener_vehiculo(VEHICULO_ID)
    assert vehiculo == identidad_client.VehiculoIdentidad(
        id=VEHICULO_ID,
        placa="ABC123",
        es_visitante=False,
        estado_verificacion="aprobado",
        propietario_id=PROPIETARIO_ID,
        propietario_estado_verificacion="pendiente",
    )
    assert str(peticiones[0].url) == f"{settings.IDENTIDAD_URL}/interno/vehiculos/{VEHICULO_ID}"

    identidad_responde(lambda peticion: httpx.Response(200, json=_vehiculo(None)))
    visitante = identidad_client.obtener_vehiculo(VEHICULO_ID)
    assert visitante.es_visitante is True
    assert visitante.propietario_id is None and visitante.propietario_estado_verificacion is None


def test_vehiculo_inexistente_no_es_lo_mismo_que_identidad_caida(identidad_responde):
    identidad_responde(lambda peticion: httpx.Response(404, json={"detail": "Vehiculo no encontrado"}))
    with pytest.raises(identidad_client.VehiculoNoEncontradoError):
        identidad_client.obtener_vehiculo(VEHICULO_ID)


def _sin_conexion(peticion):
    raise httpx.ConnectError("sin conexion", request=peticion)


def _tarda_demasiado(peticion):
    raise httpx.ReadTimeout("tardo mas de 5 segundos", request=peticion)


@pytest.mark.parametrize(
    "manejador",
    [
        _sin_conexion,
        _tarda_demasiado,
        lambda peticion: httpx.Response(500, json={"detail": "error"}),
        lambda peticion: httpx.Response(422, json={"detail": "id invalido"}),
        lambda peticion: httpx.Response(200, text="<html>no es json</html>"),
        lambda peticion: httpx.Response(200, json={"id": str(VEHICULO_ID)}),  # faltan campos
        lambda peticion: httpx.Response(200, json=["otra", "forma"]),
    ],
    ids=["sin-conexion", "timeout", "500", "422", "no-json", "faltan-campos", "otra-forma"],
)
def test_cualquier_otra_respuesta_es_identidad_no_disponible(identidad_responde, manejador):
    identidad_responde(manejador)

    with pytest.raises(identidad_client.IdentidadNoDisponibleError) as error:
        identidad_client.obtener_vehiculo(VEHICULO_ID)
    assert str(error.value) == "El servicio de identidad no esta disponible"

    with pytest.raises(identidad_client.IdentidadNoDisponibleError):
        identidad_client.usuarios_existentes([uuid.uuid4()])


def test_usuarios_existentes_devuelve_los_que_identidad_conoce(identidad_responde):
    activo, inactivo, inexistente = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    peticiones = identidad_responde(
        lambda peticion: httpx.Response(
            200,
            json=[
                {"id": str(activo), "rol": "vigilante", "activo": True},
                {"id": str(inactivo), "rol": "docente", "activo": False},
            ],
        )
    )

    # existir no depende de estar activo
    assert identidad_client.usuarios_existentes([activo, inexistente, inactivo]) == {activo, inactivo}
    assert peticiones[0].url.path == "/interno/usuarios"
    assert peticiones[0].url.params.get_list("id") == [str(activo), str(inexistente), str(inactivo)]

    # sin identificadores no hay nada que preguntar
    assert identidad_client.usuarios_existentes([]) == set()
    assert len(peticiones) == 1

    # /interno/usuarios nunca responde 404: si lo hace, algo anda mal en identidad
    identidad_responde(lambda peticion: httpx.Response(404, json={"detail": "Not Found"}))
    with pytest.raises(identidad_client.IdentidadNoDisponibleError):
        identidad_client.usuarios_existentes([activo])
