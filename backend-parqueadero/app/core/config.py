from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Claves de ejemplo publicas: con ellas el servicio no arranca.
CLAVES_DE_EJEMPLO = {"cambiar-esta-clave-en-produccion", "cambiar-esta-clave-interna"}
LARGO_MINIMO_CLAVE = 32


# Configuracion del servicio: se lee de variables de entorno (docker-compose o .env).
class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero - Zonas y cupos"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos propia del servicio: ningun otro microservicio se conecta a ella.
    DATABASE_URL: str

    # La misma clave con la que el servicio de identidad firma los tokens: aqui solo se
    # verifican, nunca se emiten.
    SECRET_KEY: str
    # Clave que accesos manda en X-Clave-Interna al llamar /interno; la misma en los tres servicios.
    CLAVE_INTERNA: str

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
