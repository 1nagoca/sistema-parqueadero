from fastapi import APIRouter

from app.api.v1.routers import accesos, auditoria

# Zonas, espacios y reportes viven en el microservicio de parqueadero (backend-parqueadero);
# inicio de sesion, usuarios, vehiculos, documentos y verificaciones, en el de identidad
# (backend-identidad).
api_router = APIRouter()
api_router.include_router(accesos.router)
api_router.include_router(auditoria.router)
