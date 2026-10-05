import logging
import uuid

from sqlalchemy import Integer, cast, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.acceso import Acceso
from app.models.enums import AccionAuditoria
from app.parqueadero_client import client as parqueadero_client
from app.schemas.acceso import AccesoEntradaCreate
from app.services import auditoria_service

logger = logging.getLogger(__name__)


class AccesoNoEncontradoOYaCerradoError(Exception):
    """No existe un acceso abierto con ese id (o ya se le registro la salida)."""


class VehiculoYaAdentroError(Exception):
    """El vehiculo ya tiene un acceso abierto: no puede entrar otra vez sin haber salido."""


INDICE_ACCESO_ACTIVO = "uq_accesos_vehiculo_activo"


def registrar_entrada(db: Session, datos: AccesoEntradaCreate, realizado_por_id: uuid.UUID) -> Acceso:
    """RN-01 + RN-03: ocupa el cupo en el servicio de parqueadero y crea el acceso junto con su
    traza de auditoria.

    El cupo y el acceso viven en bases de datos distintas, asi que no hay una transaccion que
    cubra los dos. Primero se ocupa el cupo (si no hay, el servicio lo rechaza y no se crea
    nada); si despues falla la creacion del acceso, se compensa liberando el cupo.

    Un vehiculo que ya esta adentro se rechaza antes de tocar el cupo. Si dos entradas
    simultaneas pasan esa comprobacion, el indice unico de acceso activo rechaza la segunda.
    """
    if _tiene_acceso_activo(db, datos.vehiculo_id):
        raise VehiculoYaAdentroError("El vehiculo ya tiene un acceso activo")

    parqueadero_client.ocupar_cupo(datos.zona_id, datos.espacio_id)

    try:
        acceso = Acceso(
            vehiculo_id=datos.vehiculo_id,
            usuario_id=datos.usuario_id,
            zona_id=datos.zona_id,
            espacio_id=datos.espacio_id,
            tipo_acceso=datos.tipo_acceso,
            autorizado_por_id=datos.autorizado_por_id,
            justificacion=datos.justificacion,
            placa_detectada_por_alpr=datos.placa_detectada_por_alpr,
            confianza_alpr=datos.confianza_alpr,
        )
        db.add(acceso)
        db.flush()

        auditoria_service.registrar_auditoria(
            db,
            tabla_afectada="accesos",
            registro_id=acceso.id,
            accion=AccionAuditoria.CREACION,
            realizado_por_id=realizado_por_id,
            valores_nuevos={
                "zona_id": str(datos.zona_id),
                "vehiculo_id": str(datos.vehiculo_id),
                "tipo_acceso": datos.tipo_acceso.value,
            },
        )

        db.commit()
    except IntegrityError as exc:
        db.rollback()
        _compensar(parqueadero_client.liberar_cupo, datos.zona_id, datos.espacio_id)
        diag = getattr(exc.orig, "diag", None)
        if getattr(diag, "constraint_name", None) == INDICE_ACCESO_ACTIVO:
            raise VehiculoYaAdentroError("El vehiculo ya tiene un acceso activo") from exc
        raise
    except Exception:
        db.rollback()
        _compensar(parqueadero_client.liberar_cupo, datos.zona_id, datos.espacio_id)
        raise

    db.refresh(acceso)
    return acceso


def _tiene_acceso_activo(db: Session, vehiculo_id: uuid.UUID) -> bool:
    return (
        db.query(Acceso.id)
        .filter(Acceso.vehiculo_id == vehiculo_id, Acceso.fecha_hora_salida.is_(None))
        .first()
        is not None
    )


def registrar_salida(db: Session, acceso_id: uuid.UUID, realizado_por_id: uuid.UUID) -> Acceso:
    """RN-02: cierra el acceso (fecha/duracion) y libera el cupo en el servicio de parqueadero.
    El UPDATE condicional (``WHERE fecha_hora_salida IS NULL``) hace que una segunda llamada
    sobre el mismo acceso sea un no-op idempotente en vez de un doble conteo.

    El cupo se libera antes de confirmar la salida: si el servicio de parqueadero falla, la
    salida se revierte y el acceso sigue abierto; si falla la confirmacion, se compensa
    volviendo a ocupar el cupo.
    """
    resultado = db.execute(
        update(Acceso)
        .where(Acceso.id == acceso_id, Acceso.fecha_hora_salida.is_(None))
        .values(
            fecha_hora_salida=func.now(),
            duracion_minutos=cast(
                func.extract("epoch", func.now() - Acceso.fecha_hora_entrada) / 60, Integer
            ),
        )
        .returning(Acceso)
    )
    acceso = resultado.scalar_one_or_none()
    if acceso is None:
        raise AccesoNoEncontradoOYaCerradoError(f"El acceso {acceso_id} no existe o ya fue cerrado")
    zona_id, espacio_id = acceso.zona_id, acceso.espacio_id

    try:
        parqueadero_client.liberar_cupo(zona_id, espacio_id)
    except Exception:
        db.rollback()
        raise

    try:
        auditoria_service.registrar_auditoria(
            db,
            tabla_afectada="accesos",
            registro_id=acceso.id,
            accion=AccionAuditoria.ACTUALIZACION,
            realizado_por_id=realizado_por_id,
            valores_nuevos={
                "fecha_hora_salida": acceso.fecha_hora_salida.isoformat(),
                "duracion_minutos": acceso.duracion_minutos,
            },
        )
        db.commit()
    except Exception:
        db.rollback()
        _compensar(parqueadero_client.ocupar_cupo, zona_id, espacio_id)
        raise

    db.refresh(acceso)
    return acceso


def _compensar(accion, zona_id: uuid.UUID, espacio_id: uuid.UUID | None) -> None:
    """Deshace el movimiento de cupo ya hecho en el servicio de parqueadero. Si la compensacion
    tambien falla no hay mas que hacer aqui: se deja registro para corregir el contador a mano."""
    try:
        accion(zona_id, espacio_id)
    except Exception:
        logger.exception(
            "No se pudo compensar el cupo de la zona %s (espacio %s): el contador quedo desfasado",
            zona_id,
            espacio_id,
        )
