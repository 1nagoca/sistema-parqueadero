"""Siembra del administrador y el vigilante iniciales del servicio de identidad.

    docker compose exec backend-identidad python -m app.db.seed

Los datos salen del entorno. Obligatorias: SEED_ADMIN_CORREO, SEED_ADMIN_PASSWORD,
SEED_VIGILANTE_CORREO y SEED_VIGILANTE_PASSWORD. Opcionales: SEED_ADMIN_NOMBRE,
SEED_ADMIN_DOCUMENTO, SEED_VIGILANTE_NOMBRE y SEED_VIGILANTE_DOCUMENTO.

No hay contrasena por defecto: si falta o es muy corta, no se crea ningun usuario. Es
idempotente: un correo que ya existe no se duplica ni se le cambia la contrasena. Nunca se
imprimen contrasenas ni hashes.
"""

import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field

from email_validator import EmailNotValidError, validate_email
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hashear_password
from app.db.session import SessionLocal
from app.models.enums import EstadoVerificacion, RolUsuario
from app.models.usuario import Usuario

MIN_PASSWORD = 12
# bcrypt ignora en silencio lo que pase de 72 bytes.
MAX_PASSWORD_BYTES = 72

_POR_DEFECTO = {
    "ADMIN": (RolUsuario.ADMIN, "Administrador del sistema", "SEED-ADMIN"),
    "VIGILANTE": (RolUsuario.VIGILANTE, "Vigilante de turno", "SEED-VIGILANTE"),
}


class SiembraError(Exception):
    """Los datos de siembra no sirven; no se creo ningun usuario."""


@dataclass(frozen=True)
class UsuarioSemilla:
    rol: RolUsuario
    correo: str
    # Fuera del repr para que nunca termine en un log o en un mensaje de error.
    password: str = field(repr=False)
    nombre_completo: str
    documento_identidad: str


def datos_desde_entorno(entorno: Mapping[str, str]) -> list[UsuarioSemilla]:
    usuarios = []
    for prefijo, (rol, nombre, documento) in _POR_DEFECTO.items():
        usuarios.append(
            UsuarioSemilla(
                rol=rol,
                correo=entorno.get(f"SEED_{prefijo}_CORREO", ""),
                password=entorno.get(f"SEED_{prefijo}_PASSWORD", ""),
                nombre_completo=entorno.get(f"SEED_{prefijo}_NOMBRE", "").strip() or nombre,
                documento_identidad=entorno.get(f"SEED_{prefijo}_DOCUMENTO", "").strip() or documento,
            )
        )
    return usuarios


def _validar(usuarios: list[UsuarioSemilla]) -> list[UsuarioSemilla]:
    """Devuelve los usuarios con el correo normalizado o lanza SiembraError."""
    validados = []
    for usuario in usuarios:
        rol = usuario.rol.value
        if not usuario.correo.strip():
            raise SiembraError(f"Falta el correo del {rol}")
        try:
            correo = validate_email(usuario.correo.strip(), check_deliverability=False).normalized.lower()
        except EmailNotValidError as exc:
            raise SiembraError(f"El correo del {rol} no es valido") from exc
        if not usuario.password:
            raise SiembraError(f"Falta la contrasena del {rol}: no hay contrasena por defecto")
        if len(usuario.password) < MIN_PASSWORD:
            raise SiembraError(f"La contrasena del {rol} debe tener al menos {MIN_PASSWORD} caracteres")
        if len(usuario.password.encode()) > MAX_PASSWORD_BYTES:
            raise SiembraError(f"La contrasena del {rol} no puede superar {MAX_PASSWORD_BYTES} bytes")
        validados.append(
            UsuarioSemilla(
                rol=usuario.rol,
                correo=correo,
                password=usuario.password,
                nombre_completo=usuario.nombre_completo,
                documento_identidad=usuario.documento_identidad,
            )
        )
    if len({u.correo for u in validados}) != len(validados):
        raise SiembraError("Cada usuario de la siembra necesita un correo distinto")
    return validados


def sembrar_usuarios(db: Session, usuarios: list[UsuarioSemilla]) -> list[tuple[str, RolUsuario, bool]]:
    """Crea los usuarios que no existan (por correo). Devuelve (correo, rol, creado) de cada uno.

    Todo o nada: si algun dato no sirve se lanza SiembraError y no se crea ninguno.
    """
    validados = _validar(usuarios)
    resultados = []
    try:
        for usuario in validados:
            existente = db.query(Usuario).filter(Usuario.correo_institucional == usuario.correo).first()
            if existente is not None:
                resultados.append((usuario.correo, existente.rol, False))
                continue
            ocupado = (
                db.query(Usuario).filter(Usuario.documento_identidad == usuario.documento_identidad).first()
            )
            if ocupado is not None:
                raise SiembraError(
                    f"El documento {usuario.documento_identidad} del {usuario.rol.value} ya lo usa otro usuario"
                )
            db.add(
                Usuario(
                    nombre_completo=usuario.nombre_completo,
                    correo_institucional=usuario.correo,
                    documento_identidad=usuario.documento_identidad,
                    rol=usuario.rol,
                    hashed_password=hashear_password(usuario.password),
                    estado_verificacion=EstadoVerificacion.APROBADO,
                    activo=True,
                )
            )
            db.flush()
            resultados.append((usuario.correo, usuario.rol, True))
        db.commit()
    except SiembraError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise SiembraError("El correo o el documento de la siembra ya lo usa otro usuario") from exc
    return resultados


def main() -> int:
    try:
        with SessionLocal() as db:
            resultados = sembrar_usuarios(db, datos_desde_entorno(os.environ))
    except SiembraError as exc:
        print(f"Siembra cancelada, no se creo ningun usuario: {exc}", file=sys.stderr)
        return 1
    for correo, rol, creado in resultados:
        estado = "creado" if creado else "ya existia, no se modifico"
        print(f"{correo} ({rol.value}): {estado}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
