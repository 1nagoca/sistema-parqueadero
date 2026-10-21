# Enums: listas de valores fijos; coinciden con los tipos ENUM de la base.
import enum


class RolUsuario(str, enum.Enum):
    """Roles que emite el servicio de identidad en el token (claim ``rol``)."""

    ESTUDIANTE = "estudiante"
    DOCENTE = "docente"
    ADMINISTRATIVO = "administrativo"
    VIGILANTE = "vigilante"
    ADMIN = "admin"


# Tipos de vehiculo; la base conserva todos, pero la API solo acepta motos.
class TipoVehiculo(str, enum.Enum):
    CARRO = "carro"
    MOTO = "moto"
    BICICLETA = "bicicleta"
    OTRO = "otro"


# Que tipo de cambio registra la auditoria.
class AccionAuditoria(str, enum.Enum):
    CREACION = "creacion"
    ACTUALIZACION = "actualizacion"
    ELIMINACION = "eliminacion"


# Estado de la revision del administrador.
class EstadoVerificacion(str, enum.Enum):
    PENDIENTE = "pendiente"
    APROBADO = "aprobado"
    RECHAZADO = "rechazado"


# Documentos que se pueden subir.
class TipoDocumento(str, enum.Enum):
    CARNET = "carnet"
    FOTO_PLACA = "foto_placa"
    TARJETA_PROPIEDAD = "tarjeta_propiedad"
