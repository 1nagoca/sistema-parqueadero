from datetime import time

from pydantic_settings import BaseSettings, SettingsConfigDict


# Configuracion del servicio: se lee de variables de entorno (docker-compose o .env).
class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero API"
    API_V1_PREFIX: str = "/api/v1"

    # En produccion apunta a Postgres administrado (Supabase/Neon); en desarrollo, al
    # contenedor `db` de docker-compose.
    DATABASE_URL: str

    # La misma clave con la que el servicio de identidad firma los tokens: aqui solo se
    # verifican, nunca se emiten.
    SECRET_KEY: str
    # Clave que se manda en X-Clave-Interna a /interno de identidad y parqueadero; la misma en los tres servicios.
    CLAVE_INTERNA: str = "cambiar-esta-clave-interna"

    # Direcciones internas de los otros servicios (red de Docker).
    PARQUEADERO_URL: str = "http://backend-parqueadero:8002"
    IDENTIDAD_URL: str = "http://backend-identidad:8003"

    # Horario del parqueadero en hora de Colombia; debe coincidir con el de identidad.
    HORARIO_APERTURA: time = time(5, 45)
    HORARIO_CIERRE: time = time(22, 0)
    # 24/7 desde el 2026-11-27: el horario esta desactivado; se reactiva con HORARIO_RESTRINGIDO=true.
    HORARIO_RESTRINGIDO: bool = False

    # Paginas que pueden llamar a esta API desde el navegador.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Objeto unico con la configuracion; se importa donde haga falta.
settings = Settings()
