from datetime import time

from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Claves de ejemplo publicas: con ellas el servicio no arranca.
CLAVES_DE_EJEMPLO = {"cambiar-esta-clave-en-produccion", "cambiar-esta-clave-interna"}
LARGO_MINIMO_CLAVE = 32


# Configuracion del servicio: se lee de variables de entorno (docker-compose o .env).
class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero - Identidad y verificacion"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos propia del servicio: ningun otro microservicio se conecta a ella.
    DATABASE_URL: str

    # La clave compartida con la que se firman los tokens: este servicio es el unico que los
    # emite; los demas solo los verifican.
    SECRET_KEY: str
    # Clave que accesos manda en X-Clave-Interna al llamar /interno; la misma en los tres servicios.
    CLAVE_INTERNA: str
    # El token dura 8 horas.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    # Horario del parqueadero en hora de Colombia: fuera de el los estudiantes no inician sesion.
    HORARIO_APERTURA: time = time(5, 45)
    HORARIO_CIERRE: time = time(22, 0)
    # 24/7 desde el 2026-11-27: el horario esta desactivado; se reactiva con HORARIO_RESTRINGIDO=true.
    HORARIO_RESTRINGIDO: bool = False

    # Paginas que pueden llamar a esta API desde el navegador.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Documentos de verificacion: volumen privado, nunca se sirve como estatico.
    UPLOAD_DIR: str = "/code/uploads"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024

    # Universidad habilitada para autorregistro y dominios de correo aceptados para ella.
    UNIVERSIDAD_NOMBRE: str = "Universidad Francisco de Paula Santander"
    UNIVERSIDAD_DOMINIOS_CORREO: list[str] = ["ufps.edu.co"]

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
