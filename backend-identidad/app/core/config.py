from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero - Identidad y verificacion"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos propia del servicio: ningun otro microservicio se conecta a ella.
    DATABASE_URL: str

    # La clave compartida con la que se firman los tokens. Por ahora aqui solo se verifican.
    SECRET_KEY: str

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Documentos de verificacion: volumen privado, nunca se sirve como estatico.
    UPLOAD_DIR: str = "/code/uploads"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
