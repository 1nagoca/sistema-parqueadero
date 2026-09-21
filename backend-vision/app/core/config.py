from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero Vision (ALPR)"
    API_V1_PREFIX: str = "/api/v1"
    CONFIANZA_MINIMA: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
