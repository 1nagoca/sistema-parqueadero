"""Cliente del servicio de parqueadero: la clave interna y como trata un rechazo.
No llama al servicio real: las respuestas se simulan."""

import os
import uuid

import httpx
import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from app.core.config import settings  # noqa: E402
from app.parqueadero_client import client as parqueadero_client  # noqa: E402

ZONA_ID = uuid.uuid4()
# Se guarda antes de sustituirlo.
CLIENTE_REAL = httpx.Client


@pytest.fixture
def parqueadero_responde(monkeypatch):
    """Hace que el cliente reciba lo que devuelva ``manejador`` en vez de salir a la red.
    Devuelve la lista de peticiones que se le hicieron."""

    def instalar(manejador):
        peticiones = []

        def transporte(peticion):
            peticiones.append(peticion)
            return manejador(peticion)

        monkeypatch.setattr(
            parqueadero_client.httpx,
            "Client",
            lambda **kwargs: CLIENTE_REAL(transport=httpx.MockTransport(transporte), **kwargs),
        )
        return peticiones

    return instalar


def test_cada_peticion_lleva_la_clave_interna(parqueadero_responde, monkeypatch):
    monkeypatch.setattr(settings, "CLAVE_INTERNA", "clave-de-prueba")
    peticiones = parqueadero_responde(lambda peticion: httpx.Response(200, json={}))

    parqueadero_client.ocupar_cupo(ZONA_ID, None)
    parqueadero_client.liberar_cupo(ZONA_ID, None)
    assert [p.url.path for p in peticiones] == ["/interno/cupos/ocupar", "/interno/cupos/liberar"]
    assert all(p.headers["X-Clave-Interna"] == "clave-de-prueba" for p in peticiones)


def test_clave_interna_rechazada_es_parqueadero_no_disponible(parqueadero_responde):
    parqueadero_responde(lambda peticion: httpx.Response(401, json={"detail": "Clave interna invalida"}))

    with pytest.raises(parqueadero_client.ParqueaderoNoDisponibleError):
        parqueadero_client.ocupar_cupo(ZONA_ID, None)
