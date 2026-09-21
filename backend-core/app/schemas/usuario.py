import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.models.enums import RolUsuario


class UsuarioBase(BaseModel):
    nombre_completo: str
    correo_institucional: EmailStr
    documento_identidad: str
    telefono: str | None = None
    rol: RolUsuario


class UsuarioCreate(UsuarioBase):
    password: str


class UsuarioUpdate(BaseModel):
    nombre_completo: str | None = None
    telefono: str | None = None
    activo: bool | None = None


class UsuarioRead(UsuarioBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    activo: bool
    creado_en: datetime
    actualizado_en: datetime
