import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.models.enums import EstadoVerificacion, RolUsuario


class UsuarioBase(BaseModel):
    nombre_completo: str
    correo_institucional: EmailStr
    documento_identidad: str
    telefono: str | None = None
    rol: RolUsuario


class UsuarioCreate(UsuarioBase):
    password: str = Field(min_length=8)


class EstudianteRegistro(BaseModel):
    """Autorregistro: el estudiante elige su propia contrasena; el administrador nunca la ve
    (en BD solo existe el hash). El rol siempre es ``estudiante``."""

    nombre_completo: str = Field(min_length=3, max_length=150)
    correo_institucional: EmailStr
    documento_identidad: str = Field(min_length=5, max_length=30)
    telefono: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=72)
    acepta_tratamiento_datos: bool

    @field_validator("correo_institucional")
    @classmethod
    def validar_dominio(cls, valor: str) -> str:
        valor = valor.lower()
        dominio = valor.rsplit("@", 1)[-1]
        if dominio not in settings.UNIVERSIDAD_DOMINIOS_CORREO:
            permitidos = ", ".join(f"@{d}" for d in settings.UNIVERSIDAD_DOMINIOS_CORREO)
            raise ValueError(f"Usa tu correo institucional ({permitidos})")
        return valor

    @field_validator("acepta_tratamiento_datos")
    @classmethod
    def exigir_consentimiento(cls, valor: bool) -> bool:
        if not valor:
            raise ValueError("Debes aceptar el tratamiento de datos personales para registrarte")
        return valor


class UsuarioUpdate(BaseModel):
    nombre_completo: str | None = None
    telefono: str | None = None
    activo: bool | None = None


class UsuarioRead(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    universidad: str | None
    estado_verificacion: EstadoVerificacion
    motivo_rechazo: str | None
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
