import enum


class RolUsuario(str, enum.Enum):
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


class EstadoEspacio(str, enum.Enum):
    LIBRE = "libre"
    OCUPADO = "ocupado"
    RESERVADO = "reservado"
    MANTENIMIENTO = "mantenimiento"


class TipoAcceso(str, enum.Enum):
    NORMAL = "normal"
    VISITANTE = "visitante"


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
