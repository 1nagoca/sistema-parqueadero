from datetime import time

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Claves de ejemplo publicas: con ellas el servicio no arranca.
CLAVES_DE_EJEMPLO = {"cambiar-esta-clave-en-produccion", "cambiar-esta-clave-interna"}
LARGO_MINIMO_CLAVE = 32


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
    CLAVE_INTERNA: str

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

    # Se niega a arrancar con la clave de ejemplo o con una corta, sin mostrar su valor.
    @field_validator("SECRET_KEY", "CLAVE_INTERNA")
    @classmethod
    def clave_segura(cls, valor: str, info: ValidationInfo) -> str:
        if valor in CLAVES_DE_EJEMPLO or len(valor) < LARGO_MINIMO_CLAVE:
            raise ValueError(
                f"{info.field_name} no puede ser la clave de ejemplo ni tener menos de "
                f"{LARGO_MINIMO_CLAVE} caracteres; genera una con: openssl rand -hex 32"
            )
        return valor

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)


# Objeto unico con la configuracion; se importa donde haga falta.
settings = Settings()
