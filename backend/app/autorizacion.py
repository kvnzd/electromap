"""Reglas de autorización multi-tenant: qué puede ver y editar cada usuario.

Jerarquía: empresa -> cliente -> sucursal -> tablero.
- rol 'vsc'     : ve todo.
- rol 'empresa' : ve solo los tableros de los clientes de SU empresa.
- rol 'cliente' : ve solo los tableros de SUS sucursales (no los de otros clientes
                  de la misma empresa).
Editar: solo vsc, o empresa con puede_editar = TRUE. Un cliente NUNCA edita
(la BBDD también lo impide, pero el backend no depende solo de eso).

Todo intento de acceso fuera de scope se rechaza (403) y se registra en el log
de seguridad (logs/seguridad.log).
"""
import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, select

from app.deps import get_usuario_actual
from app.models import Cliente, Sucursal, Tablero, Usuario

log_seguridad = logging.getLogger("electromap.seguridad")


def tableros_visibles(usuario: Usuario) -> Select:
    """Consulta de los tableros activos que el usuario tiene permitido ver."""
    consulta = (
        select(Tablero)
        .join(Sucursal, Tablero.sucursal_id == Sucursal.id)
        .join(Cliente, Sucursal.cliente_id == Cliente.id)
        .where(Tablero.activo.is_(True))
    )
    if usuario.rol == "vsc":
        return consulta
    if usuario.rol == "empresa":
        return consulta.where(Cliente.empresa_id == usuario.empresa_id)
    if usuario.rol == "cliente":
        return consulta.where(Sucursal.cliente_id == usuario.cliente_id)
    # Rol desconocido: no ve nada (la BBDD no lo permite, pero por seguridad).
    return consulta.where(False)


def registrar_acceso_denegado(usuario: Usuario, recurso: str) -> None:
    """Deja constancia de un intento de acceso fuera de scope."""
    log_seguridad.warning(
        "ACCESO DENEGADO usuario_id=%s usuario=%s rol=%s recurso=%s",
        usuario.id, usuario.nombre_usuario, usuario.rol, recurso,
    )


def puede_editar(usuario: Usuario) -> bool:
    if usuario.rol == "cliente":
        return False
    return usuario.rol == "vsc" or bool(usuario.puede_editar)


def requiere_editor(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
    """Dependencia para rutas que modifican datos: rechaza a quien no puede editar."""
    if not puede_editar(usuario):
        registrar_acceso_denegado(usuario, "operación de edición")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permiso para modificar datos",
        )
    return usuario
