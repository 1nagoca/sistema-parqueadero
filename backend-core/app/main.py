from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v1.routers.realtime import router as realtime_router
from app.core.config import settings

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)
# Fuera del prefijo /api/v1: el WebSocket no es un recurso REST versionado, y todo el resto
# del proyecto (.env.example, docker-compose.yml) ya asume /ws/zonas sin prefijo.
app.include_router(realtime_router)


@app.get("/health")
def health_check() -> dict:
    return {"status": "ok"}
