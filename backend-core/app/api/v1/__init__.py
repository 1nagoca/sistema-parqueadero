from fastapi import APIRouter

from app.api.v1.routers import (
    accesos,
    auditoria,
    auth,
    documentos,
    usuarios,
    vehiculos,
    verificaciones,
)

# Zonas, espacios, reportes de ocupacion y el WebSocket /ws/zonas viven en el microservicio
# de parqueadero (backend-parqueadero).
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(vehiculos.router)
api_router.include_router(documentos.router)
api_router.include_router(verificaciones.router)
api_router.include_router(accesos.router)
api_router.include_router(auditoria.router)
