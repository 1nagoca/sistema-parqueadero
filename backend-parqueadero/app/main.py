from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v1.routers.cupos import router as cupos_router
from app.api.v1.routers.realtime import router as realtime_router
from app.core.config import settings

# Aplicacion FastAPI del servicio de parqueadero.
app = FastAPI(title=settings.PROJECT_NAME)

# Permite que el frontend llame a esta API desde el navegador (CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta /api/v1, el WebSocket /ws/zonas y la API interna /interno.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
app.include_router(realtime_router)
app.include_router(cupos_router)


# GET /health: comprueba que el servicio esta vivo.
@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
