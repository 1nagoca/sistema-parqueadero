import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, verificar_clave_interna
from app.models.usuario import Usuario
from app.models.vehiculo import Vehiculo
from app.schemas.interno import UsuarioInterno, VehiculoInterno
from app.services import vehiculo_service

# API interna entre microservicios: la usa el servicio de accesos al registrar una entrada.
# El gateway no publica /interno, asi que no es alcanzable desde el navegador.
router = APIRouter(prefix="/interno", tags=["interno"], dependencies=[Depends(verificar_clave_interna)])


# GET /interno/vehiculos/{id} (lo llama accesos): placa y estado del vehiculo y de su dueno.
@router.get("/vehiculos/{vehiculo_id}", response_model=VehiculoInterno)
def obtener_vehiculo(vehiculo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Si el vehiculo existe, su placa y si el y su dueno estan aprobados."""
    vehiculo = db.get(Vehiculo, vehiculo_id)
    if vehiculo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehiculo no encontrado")
    return VehiculoInterno(
        id=vehiculo.id,
        placa=vehiculo.placa,
        es_electrica=vehiculo.es_electrica,
        numero_serie=vehiculo.numero_serie,
        es_visitante=vehiculo.es_visitante,
        estado_verificacion=vehiculo.estado_verificacion,
        propietario=vehiculo.usuario,
    )


# GET /interno/usuarios?id= (lo llama accesos): cuales de esos usuarios existen.
@router.get("/usuarios", response_model=list[UsuarioInterno])
def usuarios_existentes(id: list[uuid.UUID] = Query(default=[]), db: Session = Depends(get_db)):
    """De los identificadores pedidos, los usuarios que existen (los demas se omiten)."""
    if not id:
        return []
    return db.query(Usuario).filter(Usuario.id.in_(id)).all()


# GET /interno/usuarios/{id}/vehiculos (lo llama accesos): solo los ids de sus vehiculos.
@router.get("/usuarios/{usuario_id}/vehiculos", response_model=list[uuid.UUID])
def vehiculos_de_usuario(usuario_id: uuid.UUID, db: Session = Depends(get_db)):
    """Sin placas ni datos del dueno; un usuario sin vehiculos o inexistente da []."""
    return vehiculo_service.ids_de_vehiculos_de_usuario(db, usuario_id)
