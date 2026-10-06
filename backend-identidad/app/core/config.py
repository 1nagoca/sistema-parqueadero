from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero - Identidad y verificacion"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos propia del servicio: ningun otro microservicio se conecta a ella.
    DATABASE_URL: str

    # La clave compartida con la que se firman los tokens: este servicio es el unico que los
    # emite; los demas solo los verifican.
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Documentos de verificacion: volumen privado, nunca se sirve como estatico.
    UPLOAD_DIR: str = "/code/uploads"

    # Universidad habilitada para autorregistro y dominios de correo aceptados para ella.
    UNIVERSIDAD_NOMBRE: str = "Universidad Francisco de Paula Santander"
    UNIVERSIDAD_DOMINIOS_CORREO: list[str] = ["ufps.edu.co"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
