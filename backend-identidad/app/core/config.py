from pydantic_settings import BaseSettings, SettingsConfigDict


# Configuracion del servicio: se lee de variables de entorno (docker-compose o .env).
class Settings(BaseSettings):
    PROJECT_NAME: str = "Parqueadero - Identidad y verificacion"
    API_V1_PREFIX: str = "/api/v1"

    # Base de datos propia del servicio: ningun otro microservicio se conecta a ella.
    DATABASE_URL: str

    # La clave compartida con la que se firman los tokens: este servicio es el unico que los
    # emite; los demas solo los verifican.
    SECRET_KEY: str
    # El token dura 8 horas.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8

    # Horario de servicio para la aplicacion. El acceso a la API solo se habilita dentro de este
    # bloque para reflejar la restriccion del caso de uso del parqueadero (6:00 a. m. a 10:00 p. m.).
    TOKEN_HORARIO_INICIO: int = 6
    TOKEN_HORARIO_FIN: int = 22
    TOKEN_HORARIO_RESTRINGIDO: bool = True

    # Paginas que pueden llamar a esta API desde el navegador.
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # Documentos de verificacion: volumen privado, nunca se sirve como estatico.
    UPLOAD_DIR: str = "/code/uploads"
    MAX_UPLOAD_BYTES: int = 5 * 1024 * 1024

    # Universidad habilitada para autorregistro y dominios de correo aceptados para ella.
    UNIVERSIDAD_NOMBRE: str = "Universidad Francisco de Paula Santander"
    UNIVERSIDAD_DOMINIOS_CORREO: list[str] = ["ufps.edu.co"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Objeto unico con la configuracion; se importa donde haga falta.
settings = Settings()
