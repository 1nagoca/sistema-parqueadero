import easyocr
import numpy as np

_lector = easyocr.Reader(["es", "en"], gpu=False)


def extraer_texto(imagen: np.ndarray) -> list[tuple[str, float]]:
    """Retorna una lista de (texto, confianza) detectados en la imagen."""
    resultados = _lector.readtext(imagen)
    return [(texto, float(confianza)) for (_bbox, texto, confianza) in resultados]
