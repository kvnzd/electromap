"""Dependencias reutilizables de las rutas.

get_usuario_actual: lee el token de la petición y devuelve el usuario que la hace.
Cualquier ruta que la use queda protegida: sin token válido o con la cuenta
deshabilitada responde 401.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Cliente, Empresa, Usuario
from app.security import leer_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

_NO_AUTENTICADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Sesión inválida o expirada",
    headers={"WWW-Authenticate": "Bearer"},
)


def cuenta_habilitada(db: Session, usuario: Usuario | None) -> bool:
    """Una cuenta funciona solo si el usuario Y su empresa/cliente están activos.

    Así, al desactivar una empresa, todos sus usuarios (y los de sus clientes)
    pierden el acceso de inmediato, sin tener que desactivarlos uno por uno.
    """
    if usuario is None or not usuario.activo:
        return False
    if usuario.empresa_id is not None:
        empresa = db.get(Empresa, usuario.empresa_id)
        if empresa is None or not empresa.activo:
            return False
    if usuario.cliente_id is not None:
        cliente = db.get(Cliente, usuario.cliente_id)
        if cliente is None or not cliente.activo:
            return False
        empresa = db.get(Empresa, cliente.empresa_id)
        if empresa is None or not empresa.activo:
            return False
    return True


def get_usuario_actual(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    usuario_id = leer_token(token)
    if usuario_id is None:
        raise _NO_AUTENTICADO
    usuario = db.get(Usuario, usuario_id)
    # Usuario (o su empresa/cliente) desactivado: pierde el acceso aunque su token no haya expirado.
    if not cuenta_habilitada(db, usuario):
        raise _NO_AUTENTICADO
    return usuario
