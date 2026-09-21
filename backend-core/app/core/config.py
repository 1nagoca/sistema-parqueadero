from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero API"
    API_V1_PREFIX: str = "/api/v1"

    # En produccion apunta a Postgres administrado (Supabase/Neon); en desarrollo, al
    # contenedor `db` de docker-compose.
    DATABASE_URL: str

    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    BACKEND_VISION_URL: str = "http://backend-vision:8001"

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
