import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.interno import UsuarioInterno, VehiculoInterno

# API interna entre microservicios: la usa el servicio de accesos al registrar una entrada.
# El gateway no publica /interno, asi que no es alcanzable desde el navegador.
router = APIRouter(prefix="/interno", tags=["interno"])


@router.get("/vehiculos/{vehiculo_id}", response_model=VehiculoInterno)
def obtener_vehiculo(vehiculo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Si el vehiculo existe, su placa y si el y su dueno estan aprobados."""
    vehiculo = db.get(Vehiculo, vehiculo_id)
    if vehiculo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")
    return VehiculoInterno(
        id=vehiculo.id,
        placa=vehiculo.placa,
        es_visitante=vehiculo.es_visitante,
        estado_verificacion=vehiculo.estado_verificacion,
        propietario=vehiculo.usuario,
    )


@router.get("/usuarios", response_model=list[UsuarioInterno])
def usuarios_existentes(id: list[uuid.UUID] = Query(default=[]), db: Session = Depends(get_db)):
    """De los identificadores pedidos, los usuarios que existen (los demas se omiten)."""
    if not id:
        return []
    return db.query(Usuario).filter(Usuario.id.in_(id)).all()
