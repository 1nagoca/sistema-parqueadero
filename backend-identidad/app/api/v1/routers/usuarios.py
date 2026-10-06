import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, require_role
from app.core.security import hashear_password
from app.models.documento import Documento
from app.models.enums import EstadoVerificacion, RolUsuario, TipoDocumento
from app.models.usuario import Usuario
from app.schemas.documento import DocumentoRead
from app.schemas.usuario import UsuarioCreate, UsuarioRead
from app.services import documento_service, verificacion_service

router = APIRouter(prefix="/usuarios", tags=["usuarios"])


@router.get("/me", response_model=UsuarioRead)
def obtener_usuario_actual(usuario_actual: Usuario = Depends(get_current_user)) -> Usuario:
    """Cualquier usuario autenticado puede leer su propio perfil (usado por el frontend justo
    despues del login para saber el rol y decidir a que panel redirigir)."""
    return usuario_actual


@router.get("/me/documentos", response_model=list[DocumentoRead])
def listar_mis_documentos(
    db: Session = Depends(get_db),
    estudiante: Usuario = Depends(require_role(RolUsuario.ESTUDIANTE)),
):
    """El carnet que el estudiante ya subio (para saber si falta enviarlo)."""
    return (
        db.query(Documento)
        .filter(Documento.usuario_id == estudiante.id, Documento.tipo == TipoDocumento.CARNET)
        .all()
    )


@router.post("/me/carnet", response_model=UsuarioRead)
async def subir_carnet(
    archivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    estudiante: Usuario = Depends(require_role(RolUsuario.ESTUDIANTE)),
) -> Usuario:
    """El estudiante sube la foto de su carnet o captura de Divisist (donde se vean sus datos).
    Deja la cuenta en ``pendiente`` para que el administrador la revise; si ya fue rechazada,
    sirve para corregirla y reenviarla."""
    if estudiante.estado_verificacion == EstadoVerificacion.APROBADO:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tu identidad ya fue aprobada")
    try:
        ruta, content_type, tamano = await documento_service.guardar_archivo(archivo)
    except documento_service.ArchivoInvalidoError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    try:
        viejas = verificacion_service.reemplazar_documento(
            db,
            usuario_id=estudiante.id,
            vehiculo_id=None,
            tipo=TipoDocumento.CARNET,
            ruta=ruta,
            content_type=content_type,
            tamano=tamano,
        )
        estudiante.estado_verificacion = EstadoVerificacion.PENDIENTE
        estudiante.motivo_rechazo = None
        db.commit()
    except Exception:
        db.rollback()
        documento_service.eliminar_archivo(ruta)
        raise
    verificacion_service.borrar_archivos(viejas)
    db.refresh(estudiante)
    return estudiante


@router.post("", response_model=UsuarioRead, status_code=status.HTTP_201_CREATED)
def crear_usuario(
    datos: UsuarioCreate,
    db: Session = Depends(get_db),
    _: Usuario = Depends(require_role(RolUsuario.ADMIN)),
) -> Usuario:
    if datos.rol == RolUsuario.ESTUDIANTE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los estudiantes se registran ellos mismos (POST /auth/registro); el administrador no define su contrasena",
        )
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
