from fastapi import APIRouter

from app.api.v1.routers import (
    accesos,
    auditoria,
    auth,
    espacios,
    reportes,
    usuarios,
    vehiculos,
    zonas,
)

# realtime.router (el WebSocket /ws/zonas) se monta aparte en app/main.py, fuera de este
# prefijo /api/v1 -- ver comentario ahi.
api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(vehiculos.router)
api_router.include_router(zonas.router)
api_router.include_router(espacios.router)
api_router.include_router(accesos.router)
api_router.include_router(auditoria.router)
api_router.include_router(reportes.router)
