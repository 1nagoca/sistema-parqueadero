import gzip
import hashlib
import json
import os
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import and_, delete, func, select
from sqlalchemy.orm import Session

from app.identidad_client import client as identidad_client
from app.models.acceso import Acceso
from app.models.auditoria_acceso import AuditoriaAcceso
from app.models.enums import AccionAuditoria, RolUsuario
from app.services import auditoria_service
from app.services.auditoria_service import COLOMBIA, hoy_en_colombia, semestre_de

# Version del formato del archivo (va en la cabecera).
FORMATO_ARCHIVO = 1
# Filas que se traen de la base por vuelta al leer con cursor del servidor.
TAMANO_BLOQUE = 5_000
# Bytes que se leen por vuelta al calcular el sha256 del archivo.
BLOQUE_SHA256 = 1024 * 1024


class CierreError(Exception):
    """El cierre no se hizo; el mensaje dice por que y si quedo algun archivo."""


# Lo que hizo (o haria, en el simulacro) el cierre.
@dataclass(frozen=True)
class ResultadoCierre:
    corte: date
    accesos: int
    trazas: int
    confirmado: bool
    archivo: Path | None = None
    sha256: str | None = None


# Inicio del semestre anterior al de la fecha: lo de antes se archiva y se borra (RN-10).
def corte_para(hoy: date) -> date:
    actual = semestre_de(hoy)
    return semestre_de(actual.inicio - timedelta(days=1)).inicio


# Archiva y borra los accesos cerrados antes del corte y sus trazas; sin confirmar solo cuenta.
def cerrar_semestre(
    db: Session,
    *,
    admin_id: uuid.UUID,
    carpeta: Path,
    confirmar: bool,
    hoy: date | None = None,
) -> ResultadoCierre:
    """Orden con confirmar: archivo temporal, verificacion, sha256, nombre final y solo entonces
    el borrado con su traza en una sola transaccion. Si algo falla antes del commit no se borra
    nada; los accesos abiertos y la auditoria de identidad nunca se tocan."""
    _exigir_admin_activo(admin_id)
    corte = corte_para(hoy or hoy_en_colombia())
    limite = datetime.combine(corte, time.min, tzinfo=COLOMBIA)

    # Accesos que salen (cerrados antes del corte) y sus trazas, siempre por subconsulta, nunca con listas de ids.
    a_archivar = and_(Acceso.fecha_hora_salida.is_not(None), Acceso.fecha_hora_salida < limite)
    de_esos_accesos = and_(
        AuditoriaAcceso.tabla_afectada == "accesos",
        AuditoriaAcceso.registro_id.in_(select(Acceso.id).where(a_archivar)),
    )

    # Cuenta sin traer filas; con confirmar, el FOR UPDATE de la subconsulta los bloquea hasta el commit.
    ids_a_archivar = select(Acceso.id).where(a_archivar)
    if confirmar:
        ids_a_archivar = ids_a_archivar.with_for_update()
    accesos = db.scalar(select(func.count()).select_from(ids_a_archivar.subquery())) or 0
    trazas = db.scalar(select(func.count()).select_from(AuditoriaAcceso).where(de_esos_accesos)) or 0
    if not confirmar or not accesos:
        db.rollback()
        return ResultadoCierre(corte, accesos, trazas, confirmado=confirmar)

    # 1-3. Archivo temporal, verificacion, sha256 y nombre final.
    ahora = datetime.now(COLOMBIA)
    nombre = f"accesos-antes-de-{corte.isoformat()}-{ahora:%Y%m%dT%H%M%S}.jsonl.gz"
    final = carpeta / nombre
    temporal = carpeta / f"{nombre}.tmp"
    huella = carpeta / f"{nombre}.sha256"
    cabecera = {
        "tipo": "cabecera",
        "formato": FORMATO_ARCHIVO,
        "corte": corte.isoformat(),
        "generado_en": ahora.isoformat(timespec="seconds"),
        "accesos": accesos,
        "trazas": trazas,
    }
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
        escritas, huella_ids = _escribir_archivo(temporal, cabecera, _filas(db, a_archivar, de_esos_accesos))
        if escritas != {"accesos": accesos, "auditoria_accesos": trazas}:
            raise CierreError(f"Se escribieron {escritas}, pero se contaron {accesos} accesos y {trazas} trazas")
        _verificar_archivo(temporal, escritas, huella_ids)
        sha256 = _sha256_por_bloques(temporal)
        huella.write_text(f"{sha256}  {nombre}\n", encoding="utf-8")
        os.chmod(huella, 0o600)
        os.replace(temporal, final)
    except Exception as exc:
        db.rollback()
        temporal.unlink(missing_ok=True)
        huella.unlink(missing_ok=True)
        raise CierreError(f"No se pudo escribir o verificar el archivo ({exc}); no se borro nada") from exc

    # 4. Borrado (primero las trazas, que dependen de los accesos) y traza del borrado en una sola transaccion.
    try:
        trazas_borradas = db.execute(
            delete(AuditoriaAcceso).where(de_esos_accesos).execution_options(synchronize_session=False)
        ).rowcount
        accesos_borrados = db.execute(
            delete(Acceso).where(a_archivar).execution_options(synchronize_session=False)
        ).rowcount
        if (accesos_borrados, trazas_borradas) != (accesos, trazas):
            raise CierreError(
                f"Se iban a borrar {accesos_borrados} accesos y {trazas_borradas} trazas, "
                f"pero el archivo tiene {accesos} y {trazas}"
            )
        auditoria_service.registrar_auditoria(
            db,
            tabla_afectada="cierre_semestre",
            registro_id=uuid.uuid4(),
            accion=AccionAuditoria.ELIMINACION,
            realizado_por_id=admin_id,
            valores_nuevos={
                "corte": corte.isoformat(),
                "accesos": accesos,
                "trazas": trazas,
                "archivo": nombre,
                "sha256": sha256,
            },
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        raise CierreError(f"No se borro nada en la base ({exc}); el archivo quedo guardado en {final}") from exc

    return ResultadoCierre(corte, accesos, trazas, confirmado=True, archivo=final, sha256=sha256)


# Lineas para mostrar el resultado en la consola.
def resumen(resultado: ResultadoCierre) -> list[str]:
    anterior = semestre_de(resultado.corte)
    actual = semestre_de(anterior.fin + timedelta(days=1))
    lineas = [f"Corte: {resultado.corte.isoformat()} (se conservan {anterior.nombre} y {actual.nombre})"]
    if not resultado.confirmado:
        lineas.append(f"Por archivar: {resultado.accesos} accesos cerrados y {resultado.trazas} trazas")
        lineas.append("Simulacro: no se borro nada. Para hacerlo, repite con --confirmar.")
    elif resultado.archivo is None:
        lineas.append("Nada por archivar: no se creo archivo ni se borro nada.")
    else:
        lineas.append(f"Archivo: {resultado.archivo} (sha256 {resultado.sha256})")
        lineas.append(
            f"Borrados: {resultado.accesos} accesos y {resultado.trazas} trazas; quedo la traza cierre_semestre."
        )
        lineas.append("Copia el archivo y su .sha256 fuera del servidor (docker compose cp).")
    return lineas


# Solo un administrador activo segun identidad puede correr el cierre.
def _exigir_admin_activo(admin_id: uuid.UUID) -> None:
    try:
        usuario = identidad_client.obtener_usuario(admin_id)
    except identidad_client.IdentidadNoDisponibleError as exc:
        raise CierreError("El servicio de identidad no responde; no se hizo nada") from exc
    if usuario is None:
        raise CierreError("El --admin-id no existe en identidad")
    if usuario.rol != RolUsuario.ADMIN.value:
        raise CierreError("El --admin-id no es de un administrador")
    if not usuario.activo:
        raise CierreError("El administrador del --admin-id esta dado de baja")


# Pasa un valor de la base a algo que JSON entiende.
def _a_json(valor: Any) -> Any:
    if isinstance(valor, uuid.UUID | Decimal):
        return str(valor)
    if isinstance(valor, datetime | date):
        return valor.isoformat()
    if isinstance(valor, Enum):
        return valor.value
    return valor


# Recorre en bloques los accesos y despues sus trazas, sin guardarlos en memoria.
def _filas(db: Session, a_archivar, de_esos_accesos) -> Iterator[tuple[str, dict]]:
    consultas = (
        ("accesos", select(Acceso.__table__).where(a_archivar).order_by(Acceso.fecha_hora_salida, Acceso.id)),
        (
            "auditoria_accesos",
            select(AuditoriaAcceso.__table__)
            .where(de_esos_accesos)
            .order_by(AuditoriaAcceso.fecha_hora, AuditoriaAcceso.id),
        ),
    )
    for tabla, consulta in consultas:
        for fila in db.execute(consulta, execution_options={"yield_per": TAMANO_BLOQUE}).mappings():
            yield tabla, dict(fila)


# Escribe la cabecera y cada fila segun llega, comprimido; devuelve los conteos por tabla y el hash de los ids.
def _escribir_archivo(ruta: Path, cabecera: dict, filas: Iterator[tuple[str, dict]]) -> tuple[dict[str, int], str]:
    conteos = {"accesos": 0, "auditoria_accesos": 0}
    ids = hashlib.sha256()
    with open(ruta, "wb") as crudo:
        os.chmod(ruta, 0o600)
        with gzip.GzipFile(fileobj=crudo, mode="wb") as comprimido:
            comprimido.write((json.dumps(cabecera, ensure_ascii=False) + "\n").encode("utf-8"))
            for tabla, fila in filas:
                linea = {"tabla": tabla, "fila": {k: _a_json(v) for k, v in fila.items()}}
                comprimido.write((json.dumps(linea, ensure_ascii=False) + "\n").encode("utf-8"))
                conteos[tabla] += 1
                ids.update(f"{tabla}:{fila['id']}\n".encode())
        crudo.flush()
        os.fsync(crudo.fileno())
    return conteos, ids.hexdigest()


# Relee el archivo linea por linea y comprueba cabecera, conteos y hash de los ids.
def _verificar_archivo(ruta: Path, conteos: dict[str, int], huella_ids: str) -> None:
    leidas = {"accesos": 0, "auditoria_accesos": 0}
    ids = hashlib.sha256()
    with gzip.open(ruta, "rt", encoding="utf-8") as archivo:
        cabecera = json.loads(archivo.readline())
        for linea in archivo:
            registro = json.loads(linea)
            leidas[registro["tabla"]] += 1
            ids.update(f"{registro['tabla']}:{registro['fila']['id']}\n".encode())
    if (
        cabecera.get("tipo") != "cabecera"
        or (cabecera.get("accesos"), cabecera.get("trazas")) != (conteos["accesos"], conteos["auditoria_accesos"])
        or leidas != conteos
        or ids.hexdigest() != huella_ids
    ):
        raise CierreError("El archivo no coincide con las filas que se iban a borrar")


# sha256 del archivo leyendolo por bloques.
def _sha256_por_bloques(ruta: Path) -> str:
    resumen_sha = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        while bloque := archivo.read(BLOQUE_SHA256):
            resumen_sha.update(bloque)
    return resumen_sha.hexdigest()
