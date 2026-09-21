from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.core.config import settings
from app.pipeline.ocr import extraer_texto
from app.pipeline.postprocess import seleccionar_mejor_candidato
from app.pipeline.preprocess import preprocesar_imagen

router = APIRouter(prefix="/alpr", tags=["alpr"])


@router.post("/reconocer")
async def reconocer_placa(imagen: UploadFile = File(...)) -> dict:
    """Servicio stateless: recibe una imagen, retorna {"placa": str, "confianza": float}.
    No tiene credenciales de base de datos ni logica de negocio (RN-01/03 se validan en
    backend-core, que es quien llama a este endpoint)."""
    contenido = await imagen.read()
    try:
        imagen_procesada = preprocesar_imagen(contenido)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    candidatos = extraer_texto(imagen_procesada)
    mejor = seleccionar_mejor_candidato(candidatos)

    if mejor is None or mejor[1] < settings.CONFIANZA_MINIMA:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se detecto una placa valida en la imagen",
        )

    placa, confianza = mejor
    return {"placa": placa, "confianza": round(confianza, 2)}
