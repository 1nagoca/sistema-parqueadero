from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.auditoria_parqueadero import AuditoriaParqueadero

# Colombia no tiene horario de verano: UTC-5 fijo.
COLOMBIA = timezone(timedelta(hours=-5))
# Un semestre de julio a diciembre tiene 184 dias; un rango no puede pasar de eso.
MAX_DIAS_RANGO = 184


class RangoInvalidoError(Exception):
    """El rango de fechas pedido no se puede consultar (falta una fecha, esta al reves o es muy largo)."""


# Un semestre: su nombre (AAAA-1 o AAAA-2) y sus fechas de inicio y fin.
@dataclass(frozen=True)
class Semestre:
    nombre: str
    inicio: date
    fin: date


# Semestre de una fecha: enero a junio es AAAA-1 y julio a diciembre AAAA-2.
def semestre_de(dia: date) -> Semestre:
    if dia.month <= 6:
        return Semestre(f"{dia.year}-1", date(dia.year, 1, 1), date(dia.year, 6, 30))
    return Semestre(f"{dia.year}-2", date(dia.year, 7, 1), date(dia.year, 12, 31))


# Fecha de hoy en Colombia.
def hoy_en_colombia() -> date:
    return datetime.now(COLOMBIA).date()


# Valida el rango pedido; sin fechas usa el semestre actual.
def resolver_rango(desde: date | None, hasta: date | None) -> tuple[date, date]:
    if desde is None and hasta is None:
        semestre = semestre_de(hoy_en_colombia())
        return semestre.inicio, semestre.fin
    if desde is None or hasta is None:
        raise RangoInvalidoError("Indica las dos fechas (desde y hasta) o ninguna")
    if desde > hasta:
        raise RangoInvalidoError("La fecha desde no puede ser posterior a hasta")
    if (hasta - desde).days + 1 > MAX_DIAS_RANGO:
        raise RangoInvalidoError(
            f"El rango no puede pasar de {MAX_DIAS_RANGO} dias (un semestre); elige un periodo mas corto"
        )
    return desde, hasta


# Una pagina de trazas entre dos fechas inclusivas en hora de Colombia, de la mas nueva a la mas vieja.
def listar_auditoria(
    db: Session,
    *,
    desde: date,
    hasta: date,
    tabla_afectada: str | None,
    pagina: int,
    por_pagina: int,
) -> tuple[list[AuditoriaParqueadero], int]:
    inicio = datetime.combine(desde, time.min, tzinfo=COLOMBIA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=COLOMBIA)
    consulta = db.query(AuditoriaParqueadero).filter(
        AuditoriaParqueadero.fecha_hora >= inicio, AuditoriaParqueadero.fecha_hora < fin
    )
    if tabla_afectada is not None:
        consulta = consulta.filter(AuditoriaParqueadero.tabla_afectada == tabla_afectada)

    total = consulta.count()
    trazas = (
        consulta.order_by(AuditoriaParqueadero.fecha_hora.desc(), AuditoriaParqueadero.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )
    return trazas, total
