"""WebSocket /ws/zonas: solo avisa a conexiones que mandan un token valido en el primer mensaje.
Requiere DATABASE_URL / SECRET_KEY en el entorno; la base de pruebas la prepara conftest."""

import asyncio
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

if not os.environ.get("DATABASE_URL"):
    pytest.skip("requiere DATABASE_URL de una BD de pruebas", allow_module_level=True)

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from app.api.v1.routers import realtime  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.main import app  # noqa: E402
from app.ws.connection_manager import ConnectionManager, connection_manager  # noqa: E402

API = settings.API_V1_PREFIX


# Token como el de identidad; vence_en None lo arma sin exp.
def _jwt(rol: str = "estudiante", vence_en: float | None = 300, clave: str | None = None) -> str:
    payload: dict = {"sub": str(uuid.uuid4()), "rol": rol}
    if vence_en is not None:
        payload["exp"] = datetime.now(timezone.utc) + timedelta(seconds=vence_en)
    return jwt.encode(payload, clave or settings.SECRET_KEY, algorithm="HS256")


# Espera a que el registro tenga n conexiones (la del token se registra en el servidor, no en el test).
def _esperar_registro(n: int, limite: float = 2.0) -> None:
    fin = time.monotonic() + limite
    while len(connection_manager._conexiones) != n:
        assert time.monotonic() < fin, f"el registro tiene {len(connection_manager._conexiones)}, no {n}"
        time.sleep(0.01)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def zona(client):
    admin = {"Authorization": f"Bearer {_jwt('admin')}"}
    r = client.post(
        f"{API}/zonas", headers=admin, json={"nombre": f"Zona {uuid.uuid4().hex[:8]}", "capacidad_total": 2}
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_token_valido_recibe_el_aviso(client, zona):
    base = len(connection_manager._conexiones)
    with client.websocket_connect("/ws/zonas") as ws:
        ws.send_json({"token": _jwt("estudiante")})
        _esperar_registro(base + 1)

        assert client.post("/interno/cupos/ocupar", json={"zona_id": zona["id"]}).status_code == 200
        aviso = ws.receive_json()
        assert aviso == {"evento": "zona_actualizada", "zona_id": zona["id"], "cupos_disponibles": 1}
    _esperar_registro(base)


def test_sin_mensaje_cierra_con_4408(client, monkeypatch):
    monkeypatch.setattr(realtime, "ESPERA_TOKEN_SEGUNDOS", 0.2)
    with client.websocket_connect("/ws/zonas") as ws:
        with pytest.raises(WebSocketDisconnect) as cierre:
            ws.receive_json()
    assert cierre.value.code == 4408


@pytest.mark.parametrize(
    "mensaje",
    [
        lambda: "no-es-json",
        lambda: "{}",
        lambda: '{"token": 123}',
        lambda: '{"token": "%s"}' % _jwt(clave="otra-clave-que-no-es-la-del-servicio"),
        lambda: '{"token": "%s"}' % _jwt(rol="intruso"),
        lambda: '{"token": "%s"}' % _jwt(vence_en=-10),
        lambda: '{"token": "%s"}' % _jwt(vence_en=None),
    ],
    ids=["json-invalido", "sin-token", "token-no-texto", "firma-mala", "rol-invalido", "vencido", "sin-exp"],
)
def test_mensaje_o_token_que_no_sirve_cierra_con_4401(client, mensaje):
    base = len(connection_manager._conexiones)
    with client.websocket_connect("/ws/zonas") as ws:
        ws.send_text(mensaje())
        with pytest.raises(WebSocketDisconnect) as cierre:
            ws.receive_json()
    assert cierre.value.code == 4401
    assert len(connection_manager._conexiones) == base


def test_conexion_sin_token_no_recibe_avisos_ni_queda_registrada(client, zona, monkeypatch):
    monkeypatch.setattr(realtime, "ESPERA_TOKEN_SEGUNDOS", 1.0)
    base = len(connection_manager._conexiones)
    with client.websocket_connect("/ws/zonas") as sin_token, client.websocket_connect("/ws/zonas") as con_token:
        con_token.send_json({"token": _jwt("vigilante")})
        _esperar_registro(base + 1)

        assert client.post("/interno/cupos/ocupar", json={"zona_id": zona["id"]}).status_code == 200
        assert con_token.receive_json()["zona_id"] == zona["id"]
        assert len(connection_manager._conexiones) == base + 1
        # lo primero que le llega a la que no mando token es el cierre, no el aviso
        with pytest.raises(WebSocketDisconnect) as cierre:
            sin_token.receive_json()
        assert cierre.value.code == 4408
    _esperar_registro(base)


def test_al_vencer_el_token_cierra_con_4401_y_sale_del_registro(client):
    base = len(connection_manager._conexiones)
    with client.websocket_connect("/ws/zonas") as ws:
        # exp en segundos enteros: quedan entre 1 y 2 s
        ws.send_json({"token": _jwt("estudiante", vence_en=2 - (time.time() % 1))})
        _esperar_registro(base + 1)
        inicio = time.monotonic()
        with pytest.raises(WebSocketDisconnect) as cierre:
            ws.receive_json()
    assert cierre.value.code == 4401
    assert time.monotonic() - inicio < 3
    assert len(connection_manager._conexiones) == base


# Conexion de mentira: guarda lo que recibe o falla al enviar.
class _ConexionFalsa:
    def __init__(self, falla: bool = False) -> None:
        self.falla = falla
        self.recibidos: list[dict] = []

    async def send_json(self, mensaje: dict) -> None:
        if self.falla:
            raise RuntimeError("socket cerrado")
        self.recibidos.append(mensaje)


def test_broadcast_sigue_con_las_demas_si_una_falla_y_la_saca_del_registro():
    manager = ConnectionManager()
    primera, del_medio, tercera = _ConexionFalsa(), _ConexionFalsa(falla=True), _ConexionFalsa()
    for conexion in (primera, del_medio, tercera):
        manager.registrar(conexion)

    asyncio.run(manager.broadcast({"evento": "zona_actualizada"}))

    assert primera.recibidos == [{"evento": "zona_actualizada"}]
    assert tercera.recibidos == [{"evento": "zona_actualizada"}]
    assert manager._conexiones == [primera, tercera]


def test_broadcast_con_todas_fallando_no_lanza_y_vacia_el_registro():
    manager = ConnectionManager()
    for _ in range(3):
        manager.registrar(_ConexionFalsa(falla=True))

    asyncio.run(manager.broadcast({"evento": "zona_actualizada"}))

    assert manager._conexiones == []
