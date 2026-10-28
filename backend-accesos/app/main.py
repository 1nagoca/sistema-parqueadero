import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1 import api_router
from app.core.config import settings
from app.db.session import engine

# Mensajes del servicio en la consola, con el mismo formato que uvicorn.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(message)s")
logger = logging.getLogger(__name__)


# Al arrancar comprueba la conexion a la base y lo deja escrito en la consola.
@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        with engine.connect() as conexion:
            conexion.execute(text("SELECT 1"))
        logger.info("Accesos: base de datos %s conectada", engine.url.database)
    except Exception as exc:
        logger.error("Accesos: no se pudo conectar a la base de datos %s: %s", engine.url.database, exc)
    yield


# Aplicacion FastAPI del servicio de accesos.
app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

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
