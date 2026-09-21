from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_role
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.models.zona import Zona

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/ocupacion")
def ocupacion_por_zona(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    zonas = db.query(Zona).all()
    return [
        {
            "zona_id": str(zona.id),
            "nombre": zona.nombre,
            "capacidad_total": zona.capacidad_total,
            "cupos_disponibles": zona.cupos_disponibles,
            "porcentaje_ocupacion": round((1 - zona.cupos_disponibles / zona.capacidad_total) * 100, 1),
        }
        for zona in zonas
    ]
