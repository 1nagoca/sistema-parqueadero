import re
import uuid
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.documento import Documento
from app.models.enums import EstadoVerificacion, TipoDocumento
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.vehiculo import VehiculoCreate
from app.services import documento_service


class PropietarioNoVisibleError(Exception):
    """El vigilante no puede ver al dueno de esa placa (no se dice por que)."""


class PlacaRepetidaError(Exception):
    """Otra peticion guardo la misma placa entre la busqueda previa y el commit."""


class NumeroSerieInvalidoError(Exception):
    """El numero de serie de la moto electrica no tiene el formato aceptado."""


class NumeroSerieRepetidoError(Exception):
    """Ya hay una moto con ese numero de serie (se compara sin guiones)."""

    def __init__(self) -> None:
        super().__init__("El número de serie ya está registrado")


# Serial o VIN de fabrica: de 8 a 17 letras, numeros o guiones.
_NUMERO_SERIE = re.compile(r"^[A-Z0-9-]{8,17}$")


# El carnet que se le puede mostrar al vigilante: ruta real y tipo del archivo.
class CarnetVisible(NamedTuple):
    ruta: Path
    content_type: str


# Crea un vehiculo y lo guarda en la base.
def crear_vehiculo(db: Session, datos: VehiculoCreate) -> Vehiculo:
    vehiculo = Vehiculo(**datos.model_dump())
    db.add(vehiculo)
    # si dos peticiones llegan a la vez, el unique de la placa frena a la segunda
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise PlacaRepetidaError("La placa ya esta registrada") from exc
    db.refresh(vehiculo)
    return vehiculo


# Busca un vehiculo por placa (sin espacios y en mayusculas).
def obtener_por_placa(db: Session, placa: str) -> Vehiculo | None:
    return db.query(Vehiculo).filter(Vehiculo.placa == placa.strip().upper()).first()


# Quita todos los espacios y pasa a mayusculas.
def normalizar_numero_serie(numero_serie: str) -> str:
    return "".join(numero_serie.split()).upper()


# Devuelve el serial normalizado o NumeroSerieInvalidoError; con 17 caracteres sigue la regla del VIN.
def validar_numero_serie(numero_serie: str) -> str:
    serie = normalizar_numero_serie(numero_serie)
    if not _NUMERO_SERIE.match(serie) or (len(serie) == 17 and set(serie) & {"I", "O", "Q"}):
        raise NumeroSerieInvalidoError(
            f"El número de serie {serie} no tiene un formato válido: de 8 a 17 letras, números o guiones;"
            " si tiene 17 caracteres, sin I, O ni Q"
        )
    return serie


# Busca la moto electrica por serial: coincidencia exacta sin espacios, en mayusculas y sin guiones.
def obtener_por_serie(db: Session, numero_serie: str) -> Vehiculo | None:
    buscado = normalizar_numero_serie(numero_serie).replace("-", "")
    return db.query(Vehiculo).filter(func.replace(Vehiculo.numero_serie, "-", "") == buscado).first()


# Falla con NumeroSerieRepetidoError si ya hay una moto con ese serial.
def comprobar_serie_libre(db: Session, numero_serie: str) -> None:
    if obtener_por_serie(db, numero_serie) is not None:
        raise NumeroSerieRepetidoError()


# Ids de los vehiculos de ese usuario, del mas antiguo al mas nuevo; [] si no tiene o no existe.
def ids_de_vehiculos_de_usuario(db: Session, usuario_id: uuid.UUID) -> list[uuid.UUID]:
    filas = (
        db.query(Vehiculo.id)
        .filter(Vehiculo.usuario_id == usuario_id)
        .order_by(Vehiculo.creado_en, Vehiculo.id)
        .all()
    )
    return [fila.id for fila in filas]


# Maximo de motos a nombre de un estudiante (punto 3); cuentan en cualquier estado.
MAX_MOTOS_POR_ESTUDIANTE = 4


# El estudiante ya tiene el maximo de motos registradas.
class MaximoDeMotosError(Exception):
    pass


# Bloquea la fila del usuario hasta el commit y falla si ya tiene el maximo de motos.
def comprobar_maximo_de_motos(db: Session, usuario_id: uuid.UUID) -> None:
    db.query(Usuario.id).filter(Usuario.id == usuario_id).with_for_update().one()
    total = db.query(func.count(Vehiculo.id)).filter(Vehiculo.usuario_id == usuario_id).scalar()
    if total >= MAX_MOTOS_POR_ESTUDIANTE:
        raise MaximoDeMotosError(f"Ya tienes {MAX_MOTOS_POR_ESTUDIANTE} motos registradas, que es el maximo")


# Dueno de la moto (buscada por placa o por serial) y su carnet si el vigilante puede verlos (RN-09).
def propietario_para_vigilante(db: Session, vehiculo: Vehiculo | None) -> tuple[Usuario, CarnetVisible | None]:
    """Solo motos registradas y aprobadas cuyo dueno esta aprobado y activo; todo lo demas
    (tambien la moto que no existe, None) responde igual para no revelar el estado de motos o duenos."""
    if (
        vehiculo is None
        or vehiculo.es_visitante
        or vehiculo.usuario is None
        or vehiculo.estado_verificacion != EstadoVerificacion.APROBADO
    ):
        raise PropietarioNoVisibleError("Propietario no disponible")
    dueno = vehiculo.usuario
    if not dueno.activo or dueno.estado_verificacion != EstadoVerificacion.APROBADO:
        raise PropietarioNoVisibleError("Propietario no disponible")
    return dueno, _carnet_en_disco(db, dueno.id)


# El carnet mas reciente del dueno si el archivo esta en disco.
def _carnet_en_disco(db: Session, usuario_id: uuid.UUID) -> CarnetVisible | None:
    carnet = (
        db.query(Documento)
        .filter(
            Documento.usuario_id == usuario_id,
            Documento.tipo == TipoDocumento.CARNET,
            Documento.vehiculo_id.is_(None),
        )
        .order_by(Documento.creado_en.desc())
        .first()
    )
    if carnet is None:
        return None
    try:
        ruta = documento_service.ruta_absoluta(carnet.ruta_archivo)
    except documento_service.ArchivoInvalidoError:
        return None
    return CarnetVisible(ruta, carnet.content_type) if ruta.is_file() else None
