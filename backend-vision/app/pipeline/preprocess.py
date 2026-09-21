import cv2
import numpy as np


def preprocesar_imagen(imagen_bytes: bytes) -> np.ndarray:
    """Decodifica bytes de imagen y aplica ajustes basicos (escala de grises, ecualizacion de
    contraste) antes de pasar a la etapa de OCR."""
    arreglo = np.frombuffer(imagen_bytes, dtype=np.uint8)
    imagen = cv2.imdecode(arreglo, cv2.IMREAD_COLOR)
    if imagen is None:
        raise ValueError("No se pudo decodificar la imagen recibida")

    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.equalizeHist(gris)
    return gris
