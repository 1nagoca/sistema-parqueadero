from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# Conexion a la base de este servicio (DATABASE_URL).
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
# Fabrica de sesiones: una por peticion.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# Abre una sesion para la peticion y la cierra al terminar.
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
