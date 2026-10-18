"""Autenticación: inicio de sesión y consulta del usuario conectado."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import cuenta_habilitada, get_usuario_actual
from app.models import Usuario
from app.schemas import TokenOut, UsuarioOut
from app.security import crear_token, verificar_password

router = APIRouter(prefix="/auth", tags=["autenticación"])


@router.post("/login", response_model=TokenOut)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Recibe usuario y contraseña; si son correctos entrega un token de sesión."""
    usuario = db.scalar(select(Usuario).where(Usuario.nombre_usuario == form.username))

    # Mismo mensaje para "no existe", "contraseña incorrecta" y "desactivado":
    # así nadie puede averiguar qué nombres de usuario existen.
    if (
        usuario is None
        or not verificar_password(form.password, usuario.password_hash)
        or not cuenta_habilitada(db, usuario)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenOut(
        access_token=crear_token(usuario.id),
        usuario=UsuarioOut.model_validate(usuario),
    )


@router.get("/me", response_model=UsuarioOut)
def quien_soy(usuario: Usuario = Depends(get_usuario_actual)):
    """Devuelve los datos del usuario dueño del token (sin la contraseña)."""
    return usuario
