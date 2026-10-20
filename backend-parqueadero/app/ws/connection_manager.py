from typing import Any

from fastapi import WebSocket


# Guarda las conexiones WebSocket abiertas y les envia mensajes.
class ConnectionManager:
    """Registro en memoria de sockets conectados al mapa de zonas en tiempo real.

    Para produccion con mas de un worker/replica de este servicio, este estado deberia
    moverse a un pub/sub compartido (ej. Redis) para que el broadcast llegue a clientes
    conectados a otra instancia.
    """

    def __init__(self) -> None:
        self._conexiones: list[WebSocket] = []

    # Acepta una conexion nueva y la guarda.
    async def conectar(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._conexiones.append(websocket)

    # Quita una conexion cerrada.
    def desconectar(self, websocket: WebSocket) -> None:
        if websocket in self._conexiones:
            self._conexiones.remove(websocket)

    # Envia el mismo mensaje a todas las conexiones.
    async def broadcast(self, mensaje: dict[str, Any]) -> None:
        for conexion in list(self._conexiones):
            await conexion.send_json(mensaje)


# Unica instancia, la comparten el router y el service.
connection_manager = ConnectionManager()
