from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.ws.connection_manager import connection_manager

router = APIRouter(tags=["realtime"])


@router.websocket("/ws/zonas")
async def ws_zonas(websocket: WebSocket) -> None:
    await connection_manager.conectar(websocket)
    try:
        while True:
            # El cliente no envia comandos; solo mantenemos la conexion abierta para el broadcast.
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.desconectar(websocket)
