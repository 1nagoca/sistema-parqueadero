# Enums: listas de valores fijos; coinciden con los tipos ENUM de la base.
import enum


class RolUsuario(str, enum.Enum):
    """Roles que emite el servicio de identidad en el token (claim ``rol``)."""

    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    VIGILANTE = "vigilante"
    ADMIN = "admin"


# Estados de un espacio (definen su color en el mapa).
class EstadoEspacio(str, enum.Enum):
    LIBRE = "libre"
    OCUPADO = "ocupado"
    RESERVADO = "reservado"
    MANTENIMIENTO = "mantenimiento"
