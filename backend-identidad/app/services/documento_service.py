import uuid
from pathlib import Path

from fastapi import UploadFile

from app.core.config import settings

# Se valida el contenido real (firma de bytes), no el Content-Type declarado por el cliente.
_FIRMAS: list[tuple[bytes, str, str]] = [
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"%PDF-", "application/pdf", ".pdf"),
]


class ArchivoInvalidoError(Exception):
    """El archivo subido esta vacio, es muy grande o no es jpg/png/pdf."""


# Reconoce el tipo real del archivo por sus primeros bytes.
def _detectar_tipo(contenido: bytes) -> tuple[str, str]:
    for firma, content_type, extension in _FIRMAS:
        if contenido.startswith(firma):
            return content_type, extension
    if contenido[:4] == b"RIFF" and contenido[8:12] == b"WEBP":
        return "image/webp", ".webp"
    raise ArchivoInvalidoError("Formato no permitido: solo JPG, PNG, WEBP o PDF")


# Valida el archivo subido y lo guarda en disco con un nombre aleatorio.
async def guardar_archivo(archivo: UploadFile, permitir_pdf: bool = True) -> tuple[str, str, int]:
    """Valida y guarda el archivo con un nombre generado (nunca el que envia el cliente, para
    evitar path traversal). Devuelve (ruta_relativa, content_type, tamano_bytes)."""
    contenido = await archivo.read(settings.MAX_UPLOAD_BYTES + 1)
    if not contenido:
        raise ArchivoInvalidoError("El archivo esta vacio")
    if len(contenido) > settings.MAX_UPLOAD_BYTES:
        limite_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise ArchivoInvalidoError(f"El archivo supera el maximo de {limite_mb} MB")

    content_type, extension = _detectar_tipo(contenido)
    if content_type == "application/pdf" and not permitir_pdf:
        raise ArchivoInvalidoError("Este documento debe ser una imagen (JPG, PNG o WEBP)")

    nombre = f"{uuid.uuid4().hex}{extension}"
    directorio = Path(settings.UPLOAD_DIR)
    directorio.mkdir(parents=True, exist_ok=True)
    (directorio / nombre).write_bytes(contenido)
    return nombre, content_type, len(contenido)


# Convierte la ruta guardada en ruta real, sin salirse de la carpeta de archivos.
def ruta_absoluta(ruta_relativa: str) -> Path:
    base = Path(settings.UPLOAD_DIR).resolve()
    destino = (base / ruta_relativa).resolve()
    if base not in destino.parents:
        raise ArchivoInvalidoError("Ruta de archivo invalida")
    return destino


# Borra un archivo del disco si existe.
def eliminar_archivo(ruta_relativa: str) -> None:
    try:
        ruta_absoluta(ruta_relativa).unlink(missing_ok=True)
    except ArchivoInvalidoError:
        pass
