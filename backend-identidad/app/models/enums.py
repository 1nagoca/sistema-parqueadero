import enum


class RolUsuario(str, enum.Enum):
    """Roles que emite el servicio de identidad en el token (claim ``rol``)."""

    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    VIGILANTE = "vigilante"
    ADMIN = "admin"
