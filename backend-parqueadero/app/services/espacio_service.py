import uuid

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.espacio import Espacio


# Crea los espacios que falten de la lista y devuelve cuantos creo.
def crear_lote(db: Session, zona_id: uuid.UUID, codigos: list[str]) -> int:
    """Idempotente: los codigos que ya existen en la zona se saltan (ON CONFLICT DO NOTHING)."""
    unicos = list(dict.fromkeys(codigos))
    resultado = db.execute(
        insert(Espacio)
        .values([{"zona_id": zona_id, "codigo": codigo} for codigo in unicos])
        .on_conflict_do_nothing(constraint="uq_espacios_zona_codigo")
        .returning(Espacio.id)
    )
    creados = len(resultado.all())
    db.commit()
    return creados
