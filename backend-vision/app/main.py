from fastapi import FastAPI

from app.api.routers.alpr import router as alpr_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)
app.include_router(alpr_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
