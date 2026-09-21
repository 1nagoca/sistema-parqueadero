from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Registro en memoria de sockets conectados al mapa de zonas en tiempo real.

    Para produccion con mas de un worker/replica de backend-core, este estado deberia
    moverse a un pub/sub compartido (ej. Redis) para que el broadcast llegue a clientes
    conectados a otra instancia.
    """

    def __init__(self) -> None:
        self._conexiones: list[WebSocket] = []

    async def conectar(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._conexiones.append(websocket)

    def desconectar(self, websocket: WebSocket) -> None:
        if websocket in self._conexiones:
            self._conexiones.remove(websocket)

    async def broadcast(self, mensaje: dict[str, Any]) -> None:
        for conexion in list(self._conexiones):
            await conexion.send_json(mensaje)


connection_manager = ConnectionManager()
