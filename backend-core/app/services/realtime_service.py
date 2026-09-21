import uuid

from app.ws.connection_manager import connection_manager
from app.ws.events import ZONA_ACTUALIZADA


async def broadcast_actualizacion_zona(zona_id: uuid.UUID, cupos_disponibles: int) -> None:
    """Se llama justo despues de un commit exitoso de acceso_service, para que el mapa de
    usuarios refleje el cambio sin necesidad de polling."""
    await connection_manager.broadcast(
        {
            "evento": ZONA_ACTUALIZADA,
            "zona_id": str(zona_id),
            "cupos_disponibles": cupos_disponibles,
        }
    )
