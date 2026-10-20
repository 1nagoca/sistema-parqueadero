from fastapi import FastAPI

from app.api.routers.alpr import router as alpr_router
from app.core.config import settings

# Aplicacion FastAPI del servicio de vision (lectura de placas).
app = FastAPI(title=settings.PROJECT_NAME)
# Monta /api/v1/alpr.
app.include_router(alpr_router, prefix=settings.API_V1_PREFIX)


# GET /health: comprueba que el servicio esta vivo.
@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
