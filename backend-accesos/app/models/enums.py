# Enums: listas de valores fijos; coinciden con los tipos ENUM de la base.
import enum


# Roles de usuario (llegan en el token).
class RolUsuario(str, enum.Enum):
    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    VIGILANTE = "vigilante"
    ADMIN = "admin"


# Acceso normal o de visitante.
class TipoAcceso(str, enum.Enum):
    NORMAL = "normal"
    VISITANTE = "visitante"


# Que tipo de cambio registra la auditoria.
class AccionAuditoria(str, enum.Enum):
    CREACION = "creacion"
    ACTUALIZACION = "actualizacion"
    ELIMINACION = "eliminacion"


# Estados de verificacion (los informa identidad).
class EstadoVerificacion(str, enum.Enum):
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
