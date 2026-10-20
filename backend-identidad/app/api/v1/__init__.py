# Junta los routers de este servicio bajo /api/v1 (/interno se monta aparte en main.py).
from fastapi import APIRouter

from app.api.v1.routers import auth, documentos, usuarios, vehiculos, verificaciones

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(usuarios.router)
api_router.include_router(vehiculos.router)
api_router.include_router(documentos.router)
api_router.include_router(verificaciones.router)
