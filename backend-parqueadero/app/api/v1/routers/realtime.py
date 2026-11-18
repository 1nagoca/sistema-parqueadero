import asyncio
import json
import time

from fastapi import APIRouter, WebSocket

from app.api.deps import usuario_de_token
from app.core.security import decodificar_token
from app.ws.connection_manager import connection_manager

router = APIRouter(tags=["realtime"])

# Segundos que se espera el primer mensaje con el token.
ESPERA_TOKEN_SEGUNDOS = 5.0
# Cierre por token ausente, invalido o vencido.
CIERRE_SIN_SESION = 4401
# Cierre porque el token no llego a tiempo.
CIERRE_SIN_TOKEN_A_TIEMPO = 4408


# WebSocket /ws/zonas: con un token valido en el primer mensaje, avisa los cambios de cupos hasta que el token vence.
@router.websocket("/ws/zonas")
async def ws_zonas(websocket: WebSocket) -> None:
    await connection_manager.aceptar(websocket)
    try:
        primero = await asyncio.wait_for(websocket.receive(), ESPERA_TOKEN_SEGUNDOS)
    except TimeoutError:
        await websocket.close(code=CIERRE_SIN_TOKEN_A_TIEMPO)
        return
    if primero["type"] == "websocket.disconnect":
        return
    vence = _vencimiento(primero.get("text"))
    if vence is None:
        await websocket.close(code=CIERRE_SIN_SESION)
        return
    connection_manager.registrar(websocket)
    try:
        await asyncio.wait_for(_esperar_desconexion(websocket), vence - time.time())
    except TimeoutError:
        # se saca del registro antes de cerrar para que ningun aviso le llegue a medio cierre
        connection_manager.desconectar(websocket)
        await websocket.close(code=CIERRE_SIN_SESION)
    finally:
        connection_manager.desconectar(websocket)


# Lee y descarta lo que mande el cliente hasta que se desconecte.
async def _esperar_desconexion(websocket: WebSocket) -> None:
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


# Momento (epoch) en que vence el token del mensaje; None si el mensaje o el token no sirven.
def _vencimiento(texto: str | None) -> float | None:
    try:
        token = json.loads(texto or "")["token"]
        if not isinstance(token, str):
            return None
        usuario_de_token(token)
        return float(decodificar_token(token)["exp"])
    except (ValueError, KeyError, TypeError):
        return None
