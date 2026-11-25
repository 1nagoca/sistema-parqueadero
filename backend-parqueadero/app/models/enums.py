# Enums: listas de valores fijos; coinciden con los tipos ENUM de la base.
import enum


class RolUsuario(str, enum.Enum):
    """Roles que emite el servicio de identidad en el token (claim ``rol``). La base conserva
    docente y administrativo, pero solo se usan estudiante, vigilante y admin."""

    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    VIGILANTE = "vigilante"
    ADMIN = "admin"


# Estados de un espacio (definen su color en el mapa).
class EstadoEspacio(str, enum.Enum):
    LIBRE = "libre"
    OCUPADO = "ocupado"
    MANTENIMIENTO = "mantenimiento"


# Acciones que quedan en la auditoria (coinciden con auditoria_accion_enum de la migracion 0003).
class AccionAuditoria(str, enum.Enum):
    CREACION = "creacion"
    ACTUALIZACION = "actualizacion"
    ELIMINACION = "eliminacion"
