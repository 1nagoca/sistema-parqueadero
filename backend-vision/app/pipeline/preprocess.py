# Paso 1 del pipeline (lo llama app/api/routers/alpr.py): preparar la foto.
import cv2
import numpy as np


# Convierte la foto a grises con mas contraste para que el OCR lea mejor.
def preprocesar_imagen(imagen_bytes: bytes) -> np.ndarray:
    """Decodifica bytes de imagen y aplica ajustes basicos (escala de grises, ecualizacion de
    contraste) antes de pasar a la etapa de OCR."""
    # Convierte los bytes recibidos en una imagen.
    arreglo = np.frombuffer(imagen_bytes, dtype=np.uint8)
    imagen = cv2.imdecode(arreglo, cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError("No se pudo decodificar la imagen recibida")

    # Pasa a escala de grises y sube el contraste.
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.equalizeHist(gris)
    return gris
