import re

# Formato de placa colombiana (3 letras + 2 digitos + letra o digito). Ajustar si el
# parqueadero debe aceptar formatos de otros paises.
PATRON_PLACA = re.compile(r"^[A-Z]{3}\d{2}[A-Z0-9]$")


def normalizar_placa(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def es_placa_valida(texto: str) -> bool:
    return bool(PATRON_PLACA.match(texto))


def seleccionar_mejor_candidato(candidatos: list[tuple[str, float]]) -> tuple[str, float] | None:
    """Recibe pares (texto, confianza) de OCR, normaliza y retorna el candidato de mayor
    confianza que respete el patron de placa; None si ninguno califica."""
    validos = [
        (normalizar_placa(texto), confianza)
        for texto, confianza in candidatos
        if es_placa_valida(normalizar_placa(texto))
    ]
    if not validos:
        return None
    return max(validos, key=lambda item: item[1])
