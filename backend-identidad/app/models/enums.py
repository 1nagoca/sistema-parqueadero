import enum


class RolUsuario(str, enum.Enum):
    """Roles que emite el servicio de identidad en el token (claim ``rol``)."""

    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    VIGILANTE = "vigilante"
    ADMIN = "admin"


class TipoVehiculo(str, enum.Enum):
    CARRO = "carro"
    MOTO = "moto"
    BICICLETA = "bicicleta"
    OTRO = "otro"


class AccionAuditoria(str, enum.Enum):
    CREACION = "creacion"
    ACTUALIZACION = "actualizacion"
    ELIMINACION = "eliminacion"


class EstadoVerificacion(str, enum.Enum):
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


class TipoDocumento(str, enum.Enum):
    CARNET = "carnet"
    FOTO_PLACA = "foto_placa"
    TARJETA_PROPIEDAD = "tarjeta_propiedad"
