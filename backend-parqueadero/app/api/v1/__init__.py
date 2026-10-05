from fastapi import APIRouter

from app.api.v1.routers import espacios, reportes, zonas

# realtime.router (el WebSocket /ws/zonas) y cupos.router (API interna) se montan aparte en
# app/main.py, fuera de este prefijo /api/v1.
api_router = APIRouter()
api_router.include_router(zonas.router)
api_router.include_router(espacios.router)
api_router.include_router(reportes.router)
