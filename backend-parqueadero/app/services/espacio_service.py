import uuid

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.espacio import Espacio
from app.models.zona import Zona


# Crea los espacios que falten de la lista y sube la capacidad de la zona si hace falta.
def crear_lote(db: Session, zona_id: uuid.UUID, codigos: list[str]) -> tuple[int, Zona | None]:
    """Idempotente: los codigos que ya existen en la zona se saltan (ON CONFLICT DO NOTHING).

    Devuelve cuantos creo y la zona si su capacidad subio (None si no cambio)."""
    unicos = list(dict.fromkeys(codigos))
    resultado = db.execute(
        insert(Espacio)
        .values([{"zona_id": zona_id, "codigo": codigo} for codigo in unicos])
        .on_conflict_do_nothing(constraint="uq_espacios_zona_codigo")
        .returning(Espacio.id)
    )
    creados = len(resultado.all())

    # Capacidad = GREATEST(capacidad, puestos de la zona) y los cupos suben lo mismo; nunca baja.
    puestos = select(func.count()).select_from(Espacio).where(Espacio.zona_id == zona_id).scalar_subquery()
    zona = db.execute(
        update(Zona)
        .where(Zona.id == zona_id, Zona.capacidad_total < puestos)
        .values(
            capacidad_total=puestos,
            cupos_disponibles=Zona.cupos_disponibles + puestos - Zona.capacidad_total,
        )
        .returning(Zona)
    ).scalar_one_or_none()

    db.commit()
    if zona is not None:
        db.refresh(zona)
    return creados, zona
