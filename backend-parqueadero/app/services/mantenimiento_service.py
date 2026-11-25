import uuid
from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.auditoria_parqueadero import AuditoriaParqueadero
from app.models.enums import AccionAuditoria, EstadoEspacio
from app.models.espacio import Espacio
from app.models.mantenimiento import Mantenimiento
from app.models.zona import Zona
from app.schemas.mantenimiento import MantenimientoRead


class EspacioNoEncontradoError(Exception):
    """El puesto no existe."""


class EstadoNoPermitidoError(Exception):
    """El puesto no esta en el estado que pide la operacion: libre para el mantenimiento, en
    mantenimiento para habilitar."""


class ZonaSinCupoError(Exception):
    """La zona no tiene cupo que descontar, o ya esta en su capacidad total al devolverlo."""


# Pone un puesto libre en mantenimiento: baja un cupo, lo anota en la bitacora y deja la traza (sin commit).
def poner_en_mantenimiento(
    db: Session, espacio_id: uuid.UUID, motivo: str, admin_id: uuid.UUID
) -> tuple[Espacio, Zona]:
    espacio, zona = _bloquear(db, espacio_id)
    cambiado = db.execute(
        update(Espacio)
        .where(Espacio.id == espacio.id, Espacio.estado == EstadoEspacio.LIBRE)
        .values(estado=EstadoEspacio.MANTENIMIENTO)
        .returning(Espacio.id)
    ).scalar_one_or_none()
    if cambiado is None:
        db.refresh(espacio)
        if espacio.estado == EstadoEspacio.MANTENIMIENTO:
            raise EstadoNoPermitidoError(f"El puesto {espacio.codigo} ya esta en mantenimiento")
        raise EstadoNoPermitidoError(
            f"El puesto {espacio.codigo} esta {espacio.estado.value}: solo se pone en mantenimiento un puesto libre"
        )

    descontado = db.execute(
        update(Zona)
        .where(Zona.id == zona.id, Zona.cupos_disponibles > 0)
        .values(cupos_disponibles=Zona.cupos_disponibles - 1)
    ).rowcount
    if descontado == 0:
        raise ZonaSinCupoError(f"La zona {zona.nombre} no tiene cupos libres para descontar")

    ahora = _ahora(db)
    db.add(Mantenimiento(espacio_id=espacio.id, motivo=motivo, iniciado_por_id=admin_id, inicio=ahora))
    _trazar(
        db,
        espacio,
        realizado_por_id=admin_id,
        motivo=motivo,
        anteriores={"estado": EstadoEspacio.LIBRE.value},
        nuevos={
            "estado": EstadoEspacio.MANTENIMIENTO.value,
            **_puesto(espacio, zona),
            "motivo": motivo,
            "inicio": ahora.isoformat(),
            "iniciado_por_id": str(admin_id),
        },
    )
    return espacio, zona


# Devuelve a libre un puesto en mantenimiento: sube el cupo, lo saca de la bitacora y deja la traza (sin commit).
def habilitar(db: Session, espacio_id: uuid.UUID, admin_id: uuid.UUID) -> tuple[Espacio, Zona]:
    espacio, zona = _bloquear(db, espacio_id)
    cambiado = db.execute(
        update(Espacio)
        .where(Espacio.id == espacio.id, Espacio.estado == EstadoEspacio.MANTENIMIENTO)
        .values(estado=EstadoEspacio.LIBRE)
        .returning(Espacio.id)
    ).scalar_one_or_none()
    if cambiado is None:
        raise EstadoNoPermitidoError(f"El puesto {espacio.codigo} no esta en mantenimiento")

    devuelto = db.execute(
        update(Zona)
        .where(Zona.id == zona.id, Zona.cupos_disponibles < Zona.capacidad_total)
        .values(cupos_disponibles=Zona.cupos_disponibles + 1)
    ).rowcount
    if devuelto == 0:
        raise ZonaSinCupoError(f"La zona {zona.nombre} ya esta en su capacidad total")

    # Si el puesto quedo en mantenimiento sin bitacora (datos puestos a mano), la traza lleva esos datos vacios.
    bitacora = db.execute(
        delete(Mantenimiento).where(Mantenimiento.espacio_id == espacio.id).returning(Mantenimiento)
    ).scalar_one_or_none()
    _trazar(
        db,
        espacio,
        realizado_por_id=admin_id,
        motivo=bitacora.motivo if bitacora else None,
        anteriores={
            "estado": EstadoEspacio.MANTENIMIENTO.value,
            "motivo": bitacora.motivo if bitacora else None,
            "inicio": bitacora.inicio.isoformat() if bitacora else None,
            "iniciado_por_id": str(bitacora.iniciado_por_id) if bitacora else None,
        },
        nuevos={
            "estado": EstadoEspacio.LIBRE.value,
            **_puesto(espacio, zona),
            "fin": _ahora(db).isoformat(),
            "habilitado_por_id": str(admin_id),
        },
    )
    return espacio, zona


# Lo que esta en mantenimiento ahora, opcionalmente de una zona, del mas viejo al mas nuevo.
def listar_activos(db: Session, zona_id: uuid.UUID | None) -> list[MantenimientoRead]:
    consulta = select(Mantenimiento, Espacio).join(Espacio, Espacio.id == Mantenimiento.espacio_id)
    if zona_id is not None:
        consulta = consulta.where(Espacio.zona_id == zona_id)
    filas = db.execute(consulta.order_by(Mantenimiento.inicio, Espacio.codigo)).all()
    return [
        MantenimientoRead(
            espacio_id=espacio.id,
            codigo=espacio.codigo,
            zona_id=espacio.zona_id,
            motivo=mantenimiento.motivo,
            inicio=mantenimiento.inicio,
            iniciado_por_id=mantenimiento.iniciado_por_id,
        )
        for mantenimiento, espacio in filas
    ]


# Busca el puesto y bloquea su zona antes de tocarlo, en el mismo orden que liberar_cupo y ocupar_cupo.
def _bloquear(db: Session, espacio_id: uuid.UUID) -> tuple[Espacio, Zona]:
    espacio = db.get(Espacio, espacio_id)
    if espacio is None:
        raise EspacioNoEncontradoError("Espacio no encontrado")
    zona = db.execute(select(Zona).where(Zona.id == espacio.zona_id).with_for_update()).scalar_one()
    return espacio, zona


# Hora de la base (la de inicio de la transaccion).
def _ahora(db: Session) -> datetime:
    return db.execute(select(func.now())).scalar_one()


# Datos del puesto que van en cada traza.
def _puesto(espacio: Espacio, zona: Zona) -> dict[str, str]:
    return {"codigo": espacio.codigo, "zona_id": str(zona.id), "zona": zona.nombre}


# Guarda una traza del puesto en auditoria_parqueadero.
def _trazar(
    db: Session,
    espacio: Espacio,
    *,
    realizado_por_id: uuid.UUID,
    motivo: str | None,
    anteriores: dict,
    nuevos: dict,
) -> None:
    db.add(
        AuditoriaParqueadero(
            tabla_afectada="espacios",
            registro_id=espacio.id,
            accion=AccionAuditoria.ACTUALIZACION,
            valores_anteriores=anteriores,
            valores_nuevos=nuevos,
            realizado_por_id=realizado_por_id,
            motivo=motivo,
        )
    )
