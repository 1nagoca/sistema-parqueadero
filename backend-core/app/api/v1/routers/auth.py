from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import crear_access_token, verificar_password
from app.models.usuario import Usuario

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
