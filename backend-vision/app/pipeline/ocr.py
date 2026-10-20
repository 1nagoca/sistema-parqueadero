# Paso 2 del pipeline: leer el texto de la imagen.
import easyocr
import numpy as np

# Lector de EasyOCR (espanol e ingles, en CPU); se crea al arrancar y ahi descarga sus modelos.
_lector = easyocr.Reader(["es", "en"], gpu=False)


# Lee los textos que aparecen en la imagen, cada uno con su confianza (0 a 1).
def extraer_texto(imagen: np.ndarray) -> list[tuple[str, float]]:
    """Retorna una lista de (texto, confianza) detectados en la imagen."""
    resultados = _lector.readtext(imagen)
    return [(texto, float(confianza)) for (_bbox, texto, confianza) in resultados]
