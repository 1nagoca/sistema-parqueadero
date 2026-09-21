import httpx

from app.core.config import settings


class VisionClientError(Exception):
    """backend-vision respondio con error o no fue alcanzable."""


async def reconocer_placa(imagen_bytes: bytes, filename: str = "captura.jpg") -> dict:
    """Envia una imagen al microservicio ALPR (backend-vision) y retorna
    ``{"placa": str, "confianza": float}``.

    backend-vision solo es alcanzable en la red interna de docker-compose: no tiene
    credenciales de base de datos ni logica de negocio, es un servicio de vision stateless.
    """
    async with httpx.AsyncClient(base_url=settings.BACKEND_VISION_URL, timeout=10.0) as client:
        respuesta = await client.post(
            "/api/v1/alpr/reconocer",
            files={"imagen": (filename, imagen_bytes, "image/jpeg")},
        )
        if respuesta.status_code != 200:
            raise VisionClientError(f"backend-vision respondio {respuesta.status_code}: {respuesta.text}")
        return respuesta.json()
