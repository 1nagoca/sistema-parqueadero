# Schemas (Pydantic): la forma de los datos que entran y salen por la API de usuarios; si no cumplen, responde 422.
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.enums import EstadoVerificacion, RolUsuario


# Campos comunes de un usuario.
class UsuarioBase(BaseModel):
    nombre_completo: str
    correo_institucional: EmailStr
    documento_identidad: str
    telefono: str | None = None
    rol: RolUsuario


# Lo que envia el admin al crear un usuario (no estudiantes).
class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=8)


# Lo que envia el estudiante al registrarse.
class EstudianteRegistro(BaseModel):
    """Autorregistro: el estudiante elige su propia contrasena; el administrador nunca la ve
    (en BD solo existe el hash). El rol siempre es ``estudiante``."""

    nombre_completo: str = Field(min_length=3, max_length=150)
    correo_institucional: EmailStr
    documento_identidad: str = Field(min_length=5, max_length=30)
    telefono: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    acepta_tratamiento_datos: bool

    # Solo acepta correos de la universidad.
    @field_validator("correo_institucional")
    @classmethod
    def validar_dominio(cls, valor: str) -> str:
        valor = valor.lower()
        dominio = valor.rsplit("@", 1)[-1]
        if dominio not in settings.UNIVERSIDAD_DOMINIOS_CORREO:
            permitidos = ", ".join(f"@{d}" for d in settings.UNIVERSIDAD_DOMINIOS_CORREO)
            raise ValueError(f"Usa tu correo institucional ({permitidos})")
        return valor

    # Sin aceptar el tratamiento de datos no hay registro.
    @field_validator("acepta_tratamiento_datos")
    @classmethod
    def exigir_consentimiento(cls, valor: bool) -> bool:
        if not valor:
            raise ValueError("Debes aceptar el tratamiento de datos personales para registrarte")
        return valor


# Campos editables de un usuario (hoy ningun endpoint lo usa).
class UsuarioUpdate(BaseModel):
    nombre_completo: str | None = None
    telefono: str | None = None
    activo: bool | None = None


# Lo que devuelve la API de un usuario (nunca la contrasena).
class UsuarioRead(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    universidad: str | None
    estado_verificacion: EstadoVerificacion
    motivo_rechazo: str | None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
