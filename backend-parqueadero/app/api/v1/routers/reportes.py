from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import UsuarioToken, get_db, require_role
from app.models.enums import EstadoEspacio, RolUsuario
from app.models.espacio import Espacio
from app.models.zona import Zona

router = APIRouter(prefix="/reportes", tags=["reportes"])


# GET /reportes/ocupacion (admin): porcentaje de ocupacion de cada zona; los puestos en mantenimiento no cuentan.
@router.get("/ocupacion")
def ocupacion_por_zona(
    db: Session = Depends(get_db),
    _: UsuarioToken = Depends(require_role(RolUsuario.ADMIN)),
):
    en_mantenimiento = func.count(Espacio.id).filter(Espacio.estado == EstadoEspacio.MANTENIMIENTO)
    filas = db.execute(
        select(Zona, en_mantenimiento).outerjoin(Espacio, Espacio.zona_id == Zona.id).group_by(Zona.id)
    ).all()
    return [_ocupacion(zona, mantenimiento) for zona, mantenimiento in filas]


# Ocupados sobre los puestos que se pueden usar (capacidad menos los que estan en mantenimiento).
def _ocupacion(zona: Zona, en_mantenimiento: int) -> dict:
    utiles = zona.capacidad_total - en_mantenimiento
    ocupados = utiles - zona.cupos_disponibles
    return {
        "zona_id": str(zona.id),
        "nombre": zona.nombre,
        "capacidad_total": zona.capacidad_total,
        "cupos_disponibles": zona.cupos_disponibles,
        "en_mantenimiento": en_mantenimiento,
        "porcentaje_ocupacion": round(ocupados / utiles * 100, 1) if utiles > 0 else 0.0,
    }
