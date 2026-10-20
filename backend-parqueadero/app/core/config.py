from pydantic_settings import BaseSettings, SettingsConfigDict


# Configuracion del servicio: se lee de variables de entorno (docker-compose o .env).
class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero - Zonas y cupos"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos propia del servicio: ningun otro microservicio se conecta a ella.
    DATABASE_URL: str

    # La misma clave con la que el servicio de identidad firma los tokens: aqui solo se
    # verifican, nunca se emiten.
    SECRET_KEY: str

    # Paginas que pueden llamar a esta API desde el navegador.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Objeto unico con la configuracion; se importa donde haga falta.
settings = Settings()
