import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.security import hashear_password
from app.models.enums import RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioRead

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/me", response_model=UsuarioRead)
def obtener_usuario_actual(usuario_actual: Usuario = Depends(get_current_user)) -> Usuario:
    """Cualquier usuario autenticado puede leer su propio perfil (usado por el frontend justo
    despues del login para saber el rol y decidir a que panel redirigir)."""
    return usuario_actual


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
) -> Usuario:
    existe = db.query(Usuario).filter(Usuario.correo_institucional == datos.correo_institucional).first()
    if existe is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El correo ya esta registrado")

    usuario = Usuario(
        nombre_completo=datos.nombre_completo,
        correo_institucional=datos.correo_institucional,
        documento_identidad=datos.documento_identidad,
        telefono=datos.telefono,
        rol=datos.rol,
        hashed_password=hashear_password(datos.password),
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


@router.get("", response_model=list[UsuarioRead])
def listar_usuarios(
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
):
    return db.query(Usuario).order_by(Usuario.nombre_completo).all()


@router.get("/{usuario_id}", response_model=UsuarioRead)
def obtener_usuario(
    usuario_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN, RolUsuario.VIGILANTE)),
) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")
    return usuario
