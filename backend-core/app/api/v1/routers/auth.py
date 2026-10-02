from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import crear_access_token, hashear_password, verificar_password
from app.models.enums import EstadoVerificacion, RolUsuario
from app.models.usuario import Usuario
from app.schemas.usuario import EstudianteRegistro, UsuarioRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)) -> dict:
    usuario = db.query(Usuario).filter(Usuario.correo_institucional == form_data.username).first()
    if usuario is None or not verificar_password(form_data.password, usuario.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales invalidas")
    if not usuario.activo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario inactivo")

    token = crear_access_token(subject=str(usuario.id))
    return {"access_token": token, "token_type": "bearer"}


@router.post("/registro", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def registrar_estudiante(datos: EstudianteRegistro, db: Session = Depends(get_db)) -> Usuario:
    """Autorregistro de estudiantes. La cuenta nace ``pendiente`` hasta que un administrador
    revise el carnet; el administrador nunca conoce la contrasena (solo se guarda su hash)."""
    duplicado = (
        db.query(Usuario)
        .filter(
            (Usuario.correo_institucional == datos.correo_institucional)
            | (Usuario.documento_identidad == datos.documento_identidad)
        )
        .first()
    )
    if duplicado is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El correo o el documento ya estan registrados"
        )

    usuario = Usuario(
        nombre_completo=datos.nombre_completo.strip(),
        correo_institucional=datos.correo_institucional,
        documento_identidad=datos.documento_identidad.strip(),
        telefono=datos.telefono,
        rol=RolUsuario.ESTUDIANTE,
        hashed_password=hashear_password(datos.password),
        universidad=settings.UNIVERSIDAD_NOMBRE,
        estado_verificacion=EstadoVerificacion.PENDIENTE,
        consentimiento_datos_en=datetime.now(timezone.utc),
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="El correo o el documento ya estan registrados"
        ) from exc
    db.refresh(usuario)
    return usuario
