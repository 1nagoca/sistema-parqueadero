import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.acceso import Acceso
from app.models.auditoria_acceso import AuditoriaAcceso
from app.models.enums import AccionAuditoria
from app.parqueadero_client import client as parqueadero_client
from app.schemas.auditoria_acceso import DetalleAcceso


# Guarda una traza en la bitacora (sin commit: lo hace quien la llama).
def registrar_auditoria(
    db: Session,
    *,
    tabla_afectada: str,
    registro_id: uuid.UUID,
    accion: AccionAuditoria,
    realizado_por_id: uuid.UUID,
    valores_anteriores: dict[str, Any] | None = None,
    valores_nuevos: dict[str, Any] | None = None,
    motivo: str | None = None,
    ip_origen: str | None = None,
) -> AuditoriaAcceso:
    """RN-04: escribe la traza dentro de la misma transaccion que la mutacion de negocio.

    No hace commit: el caller (acceso_service, etc.) controla la transaccion para que la
    mutacion y su traza de auditoria vivan o mueran juntas.
    """
    entrada = AuditoriaAcceso(
        tabla_afectada=tabla_afectada,
        registro_id=registro_id,
        accion=accion,
        valores_anteriores=valores_anteriores,
        valores_nuevos=valores_nuevos,
        realizado_por_id=realizado_por_id,
        motivo=motivo,
        ip_origen=ip_origen,
    )
    db.add(entrada)
    db.flush()
    return entrada


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


# Una pagina de trazas entre dos fechas inclusivas en hora de Colombia, de la mas nueva a la mas vieja, con su detalle.
def listar_auditoria(
    db: Session,
    *,
    desde: date,
    hasta: date,
    tabla_afectada: str | None,
    pagina: int,
    por_pagina: int,
) -> tuple[list[tuple[AuditoriaAcceso, DetalleAcceso | None]], int]:
    inicio = datetime.combine(desde, time.min, tzinfo=COLOMBIA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=COLOMBIA)
    consulta = db.query(AuditoriaAcceso).filter(
        AuditoriaAcceso.fecha_hora >= inicio, AuditoriaAcceso.fecha_hora < fin
    )
    if tabla_afectada is not None:
        consulta = consulta.filter(AuditoriaAcceso.tabla_afectada == tabla_afectada)

    total = consulta.count()
    # LEFT JOIN por la llave del acceso: solo trazas de la tabla accesos, sin una consulta por fila.
    filas = (
        consulta.outerjoin(
            Acceso,
            and_(AuditoriaAcceso.tabla_afectada == "accesos", Acceso.id == AuditoriaAcceso.registro_id),
        )
        .add_columns(
            Acceso.id.label("acceso_id"),
            Acceso.placa,
            Acceso.es_electrica,
            Acceso.numero_serie,
            Acceso.tipo_acceso,
            Acceso.zona_id,
            Acceso.espacio_id,
            Acceso.duracion_minutos,
        )
        .order_by(AuditoriaAcceso.fecha_hora.desc(), AuditoriaAcceso.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )
    codigos = _codigos_de_la_pagina([fila.espacio_id for fila in filas if fila.espacio_id is not None])
    return [(fila[0], _detalle(fila, codigos)) for fila in filas], total


# Codigos de los puestos de la pagina en una sola llamada; sin parqueadero, sin codigos (es de cortesia).
def _codigos_de_la_pagina(espacio_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    distintos = list(dict.fromkeys(espacio_ids))
    if not distintos:
        return {}
    try:
        return parqueadero_client.codigos_de_espacios(distintos)
    except parqueadero_client.ParqueaderoNoDisponibleError:
        return {}


# Detalle de una traza de acceso; None si no es de un acceso o el acceso ya no existe (se mira el id, no la placa).
def _detalle(fila, codigos: dict[uuid.UUID, str]) -> DetalleAcceso | None:
    traza = fila[0]
    if fila.acceso_id is None:
        return None
    return DetalleAcceso(
        placa=fila.placa,
        es_electrica=fila.es_electrica,
        numero_serie=fila.numero_serie,
        tipo_acceso=fila.tipo_acceso,
        zona_id=fila.zona_id,
        espacio_codigo=codigos.get(fila.espacio_id),
        # La duracion es de la salida: la traza de la entrada no la lleva aunque el acceso ya este cerrado.
        duracion_minutos=fila.duracion_minutos if traza.accion == AccionAuditoria.ACTUALIZACION else None,
    )
