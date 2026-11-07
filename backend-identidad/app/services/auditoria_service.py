import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session, aliased

from app.models.auditoria_identidad import AuditoriaIdentidad
from app.models.enums import AccionAuditoria
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.auditoria_identidad import DetalleVerificacion


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
) -> AuditoriaIdentidad:
    """Escribe la traza dentro de la misma transaccion que la mutacion de negocio.

    No hace commit: el caller (verificacion_service) controla la transaccion para que la
    mutacion y su traza de auditoria vivan o mueran juntas.
    """
    entrada = AuditoriaIdentidad(
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


# Una pagina de trazas entre dos fechas inclusivas en hora de Colombia, de la mas nueva a la mas vieja, con su detalle y autor.
def listar_auditoria(
    db: Session,
    *,
    desde: date,
    hasta: date,
    tabla_afectada: str | None,
    pagina: int,
    por_pagina: int,
) -> tuple[list[tuple[AuditoriaIdentidad, DetalleVerificacion | None, str | None]], int]:
    inicio = datetime.combine(desde, time.min, tzinfo=COLOMBIA)
    fin = datetime.combine(hasta + timedelta(days=1), time.min, tzinfo=COLOMBIA)
    consulta = db.query(AuditoriaIdentidad).filter(
        AuditoriaIdentidad.fecha_hora >= inicio, AuditoriaIdentidad.fecha_hora < fin
    )
    if tabla_afectada is not None:
        consulta = consulta.filter(AuditoriaIdentidad.tabla_afectada == tabla_afectada)

    total = consulta.count()

    # LEFT JOIN por llave: el usuario o el vehiculo afectado, el dueno del vehiculo y quien hizo la traza.
    afectado, dueno, autor = aliased(Usuario), aliased(Usuario), aliased(Usuario)
    filas = (
        consulta.outerjoin(
            afectado,
            and_(AuditoriaIdentidad.tabla_afectada == "usuarios", afectado.id == AuditoriaIdentidad.registro_id),
        )
        .outerjoin(
            Vehiculo,
            and_(AuditoriaIdentidad.tabla_afectada == "vehiculos", Vehiculo.id == AuditoriaIdentidad.registro_id),
        )
        .outerjoin(dueno, dueno.id == Vehiculo.usuario_id)
        .outerjoin(autor, autor.id == AuditoriaIdentidad.realizado_por_id)
        .add_columns(
            afectado.nombre_completo.label("afectado_nombre"),
            afectado.rol.label("afectado_rol"),
            Vehiculo.placa.label("placa"),
            dueno.nombre_completo.label("dueno_nombre"),
            dueno.rol.label("dueno_rol"),
            autor.nombre_completo.label("autor_nombre"),
        )
        .order_by(AuditoriaIdentidad.fecha_hora.desc(), AuditoriaIdentidad.id.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
        .all()
    )
    return [(fila[0], _detalle(fila), fila.autor_nombre) for fila in filas], total


# Detalle de una traza segun su tabla; None si no es de usuarios o vehiculos o el registro no existe.
def _detalle(fila) -> DetalleVerificacion | None:
    if fila.afectado_nombre is not None:
        return DetalleVerificacion(nombre=fila.afectado_nombre, rol=fila.afectado_rol, placa=None)
    if fila.placa is not None:
        return DetalleVerificacion(nombre=fila.dueno_nombre, rol=fila.dueno_rol, placa=fila.placa)
    return None
