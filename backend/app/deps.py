"""Dependencias reutilizables de las rutas.

get_usuario_actual: lee el token de la petición y devuelve el usuario que la hace.
Cualquier ruta que la use queda protegida: sin token válido responde 401.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Usuario
from app.security import leer_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sesión inválida o expirada",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    usuario_id = leer_token(token)
    if usuario_id is None:
        raise _NO_AUTENTICADO
    usuario = db.get(Usuario, usuario_id)
    # Un usuario desactivado (soft delete) pierde el acceso aunque su token no haya expirado.
    if usuario is None or not usuario.activo:
        raise _NO_AUTENTICADO
    return usuario
