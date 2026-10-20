from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.core.config import settings

# Aplicacion FastAPI del servicio de accesos.
app = FastAPI(title=settings.PROJECT_NAME)

# Permite que el frontend llame a esta API desde el navegador (CORS).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Monta los endpoints bajo /api/v1.
app.include_router(api_router, prefix=settings.API_V1_PREFIX)


# GET /health: comprueba que el servicio esta vivo.
@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
