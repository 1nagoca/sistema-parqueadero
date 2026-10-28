import logging
import uuid
from datetime import datetime

from sqlalchemy import Integer, cast, func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.identidad_client import client as identidad_client
from app.models.acceso import Acceso
from app.models.enums import AccionAuditoria, EstadoVerificacion, TipoAcceso
from app.parqueadero_client import client as parqueadero_client
from app.schemas.acceso import AccesoEntradaCreate
from app.services import auditoria_service
from app.services.auditoria_service import COLOMBIA

logger = logging.getLogger(__name__)


class AccesoNoEncontradoOYaCerradoError(Exception):
    """No existe un acceso abierto con ese id (o ya se le registro la salida)."""


class VehiculoNoVerificadoError(Exception):
    """El vehiculo o su propietario aun no estan aprobados por el administrador."""


class UsuarioNoEncontradoError(Exception):
    """El conductor o quien autoriza el ingreso no existe en el servicio de identidad."""


class VehiculoYaAdentroError(Exception):
    """El vehiculo ya tiene un acceso abierto: no puede entrar otra vez sin haber salido."""


class ParqueaderoCerradoError(Exception):
    """Fuera del horario del parqueadero no se registran entradas (RN-11)."""


# Nombre del indice que impide dos accesos abiertos del mismo vehiculo.
INDICE_ACCESO_ACTIVO = "uq_accesos_vehiculo_activo"


# Hora actual en Colombia; unico punto que los tests fijan con monkeypatch.
def ahora_en_colombia() -> datetime:
    return datetime.now(COLOMBIA)


# Abierto de HORARIO_APERTURA a HORARIO_CIERRE (el cierre ya cuenta como cerrado).
def parqueadero_abierto(ahora: datetime) -> bool:
    if not settings.HORARIO_RESTRINGIDO:
        return True
    return settings.HORARIO_APERTURA <= ahora.astimezone(COLOMBIA).time() < settings.HORARIO_CIERRE


# Registra la entrada de un vehiculo: valida, ocupa el cupo y guarda el acceso.
def registrar_entrada(db: Session, datos: AccesoEntradaCreate, realizado_por_id: uuid.UUID) -> Acceso:
    """RN-01 + RN-03: ocupa el cupo en el servicio de parqueadero y crea el acceso junto con su
    traza de auditoria.

    El cupo y el acceso viven en bases de datos distintas, asi que no hay una transaccion que
    cubra los dos. Primero se ocupa el cupo (si no hay, el servicio lo rechaza y no se crea
    nada); si despues falla la creacion del acceso, se compensa liberando el cupo.

    El vehiculo y los usuarios se consultan al servicio de identidad: si no responde, la
    entrada se rechaza (identidad_client.IdentidadNoDisponibleError) porque no se puede
    comprobar nada. Un vehiculo que no existe, que no esta verificado o que ya esta adentro se
    rechaza antes de tocar el cupo. Si dos entradas simultaneas pasan esa comprobacion, el
    indice unico de acceso activo rechaza la segunda.

    Fuera del horario del parqueadero (RN-11) se rechaza antes de todo: no se consulta a
    identidad ni se toca el cupo.
    """
    # 0. Fuera de horario no entra nadie, sea normal o visitante (RN-11).
    if not parqueadero_abierto(ahora_en_colombia()):
        raise ParqueaderoCerradoError(
            f"El parqueadero esta cerrado: las entradas se registran de "
            f"{settings.HORARIO_APERTURA:%H:%M} a {settings.HORARIO_CIERRE:%H:%M}"
        )

    # 1. Pregunta a identidad por el vehiculo y valida que pueda entrar.
    vehiculo = identidad_client.obtener_vehiculo(datos.vehiculo_id)
    _exigir_vehiculo_verificado(vehiculo, datos.tipo_acceso)
    _exigir_usuarios_existentes(datos)
    if _tiene_acceso_activo(db, datos.vehiculo_id):
        raise VehiculoYaAdentroError("El vehiculo ya tiene un acceso activo")

    # 2. Pide al servicio de parqueadero que ocupe el cupo.
    parqueadero_client.ocupar_cupo(datos.zona_id, datos.espacio_id)

    # 3. Guarda el acceso y su auditoria; si algo falla, devuelve el cupo.
    try:
        acceso = Acceso(
            vehiculo_id=datos.vehiculo_id,
            placa=vehiculo.placa,
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
    logger.info("Accesos: entrada registrada de la moto %s (%s)", acceso.placa, acceso.tipo_acceso.value)
    return acceso


# Rechaza la entrada normal si el dueno esta dado de baja o si el vehiculo o su dueno no estan aprobados.
def _exigir_vehiculo_verificado(vehiculo: identidad_client.VehiculoIdentidad, tipo_acceso: TipoAcceso) -> None:
    """Un acceso normal exige vehiculo y propietario aprobados por el administrador y un
    propietario activo (RN-03); el visitante ya pasa por su propio flujo de autorizacion +
    justificacion."""
    if tipo_acceso != TipoAcceso.NORMAL:
        return
    if vehiculo.propietario_id is not None and not vehiculo.propietario_activo:
        raise VehiculoNoVerificadoError("El propietario de la moto esta dado de baja")
    aprobado = EstadoVerificacion.APROBADO.value
    if vehiculo.estado_verificacion != aprobado or (
        vehiculo.propietario_id is not None and vehiculo.propietario_estado_verificacion != aprobado
    ):
        raise VehiculoNoVerificadoError(
            "El vehiculo o su propietario aun no estan verificados por el administrador"
        )


# Comprueba en identidad que el conductor y quien autoriza existan.
def _exigir_usuarios_existentes(datos: AccesoEntradaCreate) -> None:
    """El conductor y quien autoriza deben existir en identidad (no importa si estan activos)."""
    pedidos = [i for i in (datos.usuario_id, datos.autorizado_por_id) if i is not None]
    if not pedidos:
        return
    existentes = identidad_client.usuarios_existentes(pedidos)
    if datos.usuario_id is not None and datos.usuario_id not in existentes:
        raise UsuarioNoEncontradoError("El conductor (usuario_id) no existe")
    if datos.autorizado_por_id is not None and datos.autorizado_por_id not in existentes:
        raise UsuarioNoEncontradoError("Quien autoriza (autorizado_por_id) no existe")


# Dice si el vehiculo ya esta adentro (tiene un acceso sin salida).
def _tiene_acceso_activo(db: Session, vehiculo_id: uuid.UUID) -> bool:
    return (
        db.query(Acceso.id)
        .filter(Acceso.vehiculo_id == vehiculo_id, Acceso.fecha_hora_salida.is_(None))
        .first()
        is not None
    )


# Registra la salida: cierra el acceso, calcula la duracion y libera el cupo.
def registrar_salida(db: Session, acceso_id: uuid.UUID, realizado_por_id: uuid.UUID) -> Acceso:
    """RN-02: cierra el acceso (fecha/duracion) y libera el cupo en el servicio de parqueadero.
    El UPDATE condicional (``WHERE fecha_hora_salida IS NULL``) hace que una segunda llamada
    sobre el mismo acceso sea un no-op idempotente en vez de un doble conteo.

    El cupo se libera antes de confirmar la salida: si el servicio de parqueadero falla, la
    salida se revierte y el acceso sigue abierto; si falla la confirmacion, se compensa
    volviendo a ocupar el cupo.
    """
    # 1. Cierra el acceso solo si sigue abierto.
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

    # 2. Libera el cupo en el servicio de parqueadero.
    try:
        parqueadero_client.liberar_cupo(zona_id, espacio_id)
    except Exception:
        db.rollback()
        raise

    # 3. Guarda la auditoria; si falla, vuelve a ocupar el cupo.
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
    logger.info("Accesos: salida registrada de la moto %s tras %s min", acceso.placa, acceso.duracion_minutos)
    return acceso


# Deshace el cambio de cupo cuando algo fallo despues.
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
