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
    # Fuera del plano de 800 (punto 5): se conserva para el historial, no se lista ni se ocupa.
    RETIRADO = "retirado"


# Estados de los puestos del plano (sin los retirados). Se filtra por estos y no por "distinto de
# retirado" para que la consulta sirva tambien en una base que aun no tiene la migracion 0004.
ESTADOS_DEL_PLANO = (EstadoEspacio.LIBRE, EstadoEspacio.OCUPADO, EstadoEspacio.MANTENIMIENTO)


# Acciones que quedan en la auditoria (coinciden con auditoria_accion_enum de la migracion 0003).
class AccionAuditoria(str, enum.Enum):
    CREACION = "creacion"
    ACTUALIZACION = "actualizacion"
    ELIMINACION = "eliminacion"
