import uuid

from sqlalchemy import Integer, cast, func, update
from sqlalchemy.orm import Session

from app.models.acceso import Acceso
from app.models.enums import AccionAuditoria
from app.schemas.acceso import AccesoEntradaCreate
from app.services import auditoria_service, zona_service


class AccesoNoEncontradoOYaCerradoError(Exception):
    """No existe un acceso abierto con ese id (o ya se le registro la salida)."""


def registrar_entrada(db: Session, datos: AccesoEntradaCreate, realizado_por_id: uuid.UUID) -> Acceso:
    """RN-01 + RN-03: ocupa el cupo atomicamente y crea el acceso junto con su traza de
    auditoria dentro de una unica transaccion. Si la zona no tiene cupo o el espacio no esta
    libre, ``zona_service`` lanza y la transaccion se revierte sin crear el acceso.
    """
    zona_service.ocupar_cupo(db, datos.zona_id, datos.espacio_id)

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
    db.refresh(acceso)
    return acceso


def registrar_salida(db: Session, acceso_id: uuid.UUID, realizado_por_id: uuid.UUID) -> Acceso:
    """RN-02: cierra el acceso (fecha/duracion) y libera el cupo atomicamente, dentro de una
    unica transaccion. El UPDATE condicional (``WHERE fecha_hora_salida IS NULL``) hace que una
    segunda llamada sobre el mismo acceso sea un no-op idempotente en vez de un doble conteo.
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

    zona_service.liberar_cupo(db, acceso.zona_id, acceso.espacio_id)

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
    db.refresh(acceso)
    return acceso
