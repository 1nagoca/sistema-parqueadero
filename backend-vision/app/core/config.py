from pydantic_settings import BaseSettings, SettingsConfigDict


# Configuracion del servicio: se lee de variables de entorno (docker-compose o .env).
class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero Vision (ALPR)"
    API_V1_PREFIX: str = "/api/v1"
    # Por debajo de esta confianza no se acepta la placa leida.
    CONFIANZA_MINIMA: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Objeto unico con la configuracion; se importa donde haga falta.
settings = Settings()
