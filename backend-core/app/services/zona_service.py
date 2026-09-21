import uuid

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models.enums import EstadoEspacio
from app.models.espacio import Espacio
from app.models.zona import Zona


class SinCuposDisponiblesError(Exception):
    """La zona no tiene cupos disponibles (RN-01: se prohibe el ingreso)."""


class EspacioNoDisponibleError(Exception):
    """El espacio individual solicitado no esta libre."""


class ZonaEnCapacidadTotalError(Exception):
    """La zona ya esta en su capacidad total; liberar un cupo mas violaria el CHECK de BD."""


def ocupar_cupo(db: Session, zona_id: uuid.UUID, espacio_id: uuid.UUID | None) -> Zona:
    """RN-01: decremento atomico del contador de cupos de la zona.

    Usa un UPDATE condicional (``WHERE cupos_disponibles > 0``) en vez de un SELECT ... FOR
    UPDATE + check-then-write: es un solo round-trip y el bloqueo de fila de Postgres hace el
    read-modify-write atomico de forma implicita, sin depender de que el caller recuerde
    bloquear la fila.
    """
    resultado = db.execute(
        update(Zona)
        .where(Zona.id == zona_id, Zona.cupos_disponibles > 0)
        .values(cupos_disponibles=Zona.cupos_disponibles - 1)
        .returning(Zona)
    )
    zona = resultado.scalar_one_or_none()
    if zona is None:
        raise SinCuposDisponiblesError(f"La zona {zona_id} no tiene cupos disponibles")

    if espacio_id is not None:
        espacio_resultado = db.execute(
            update(Espacio)
            .where(Espacio.id == espacio_id, Espacio.estado == EstadoEspacio.LIBRE)
            .values(estado=EstadoEspacio.OCUPADO)
            .returning(Espacio)
        )
        if espacio_resultado.scalar_one_or_none() is None:
            raise EspacioNoDisponibleError(f"El espacio {espacio_id} no esta libre")

    return zona


def liberar_cupo(db: Session, zona_id: uuid.UUID, espacio_id: uuid.UUID | None) -> Zona:
    """RN-02: incremento atomico del contador de cupos de la zona."""
    resultado = db.execute(
        update(Zona)
        .where(Zona.id == zona_id, Zona.cupos_disponibles < Zona.capacidad_total)
        .values(cupos_disponibles=Zona.cupos_disponibles + 1)
        .returning(Zona)
    )
    zona = resultado.scalar_one_or_none()
    if zona is None:
        raise ZonaEnCapacidadTotalError(f"La zona {zona_id} ya esta en su capacidad total")

    if espacio_id is not None:
        db.execute(update(Espacio).where(Espacio.id == espacio_id).values(estado=EstadoEspacio.LIBRE))

    return zona
