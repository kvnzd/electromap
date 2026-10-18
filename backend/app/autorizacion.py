"""Reglas de autorización multi-tenant: qué puede ver y editar cada usuario.

Jerarquía: empresa -> cliente -> sucursal -> tablero.
- rol 'vsc'     : ve y administra todo.
- rol 'empresa' : ve solo lo de SU empresa (sus clientes, sucursales y tableros).
                  Puede administrarlo solo si puede_editar = TRUE.
- rol 'cliente' : ve solo lo suyo (sus sucursales y tableros). NUNCA edita
                  (la BBDD también lo impide, pero el backend no depende solo de eso).

Todo intento fuera de scope se rechaza (403) y se registra en logs/seguridad.log.
Las acciones de administración se registran en logs/auditoria.log.
"""
import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.deps import get_usuario_actual
from app.models import Cliente, Empresa, Sucursal, Tablero, Usuario

log_seguridad = logging.getLogger("electromap.seguridad")
log_auditoria = logging.getLogger("electromap.auditoria")


# ---------- Registro ----------

def registrar_acceso_denegado(usuario: Usuario, recurso: str) -> None:
    """Deja constancia de un intento de acceso fuera de scope."""
    log_seguridad.warning(
        "ACCESO DENEGADO usuario_id=%s usuario=%s rol=%s recurso=%s",
        usuario.id, usuario.nombre_usuario, usuario.rol, recurso,
    )


def registrar_auditoria(usuario: Usuario, accion: str) -> None:
    """Deja constancia de una acción de administración (quién hizo qué)."""
    log_auditoria.info(
        "por usuario_id=%s usuario=%s rol=%s: %s",
        usuario.id, usuario.nombre_usuario, usuario.rol, accion,
    )


# ---------- Qué puede VER cada usuario ----------

def _solo_activos(consulta: Select, modelo, incluir_inactivos: bool) -> Select:
    return consulta if incluir_inactivos else consulta.where(modelo.activo.is_(True))


def empresas_visibles(usuario: Usuario, incluir_inactivos: bool = False) -> Select:
    consulta = _solo_activos(select(Empresa), Empresa, incluir_inactivos)
    if usuario.rol == "vsc":
        return consulta
    if usuario.rol == "empresa":
        return consulta.where(Empresa.id == usuario.empresa_id)
    if usuario.rol == "cliente":
        empresa_del_cliente = select(Cliente.empresa_id).where(Cliente.id == usuario.cliente_id)
        return consulta.where(Empresa.id.in_(empresa_del_cliente))
    return consulta.where(False)


def clientes_visibles(usuario: Usuario, incluir_inactivos: bool = False) -> Select:
    consulta = _solo_activos(select(Cliente), Cliente, incluir_inactivos)
    if usuario.rol == "vsc":
        return consulta
    if usuario.rol == "empresa":
        return consulta.where(Cliente.empresa_id == usuario.empresa_id)
    if usuario.rol == "cliente":
        return consulta.where(Cliente.id == usuario.cliente_id)
    return consulta.where(False)


def sucursales_visibles(usuario: Usuario, incluir_inactivos: bool = False) -> Select:
    consulta = _solo_activos(
        select(Sucursal).join(Cliente, Sucursal.cliente_id == Cliente.id), Sucursal, incluir_inactivos
    )
    if usuario.rol == "vsc":
        return consulta
    if usuario.rol == "empresa":
        return consulta.where(Cliente.empresa_id == usuario.empresa_id)
    if usuario.rol == "cliente":
        return consulta.where(Sucursal.cliente_id == usuario.cliente_id)
    return consulta.where(False)


def tableros_visibles(usuario: Usuario, incluir_inactivos: bool = False) -> Select:
    consulta = _solo_activos(
        select(Tablero)
        .join(Sucursal, Tablero.sucursal_id == Sucursal.id)
        .join(Cliente, Sucursal.cliente_id == Cliente.id),
        Tablero,
        incluir_inactivos,
    )
    if usuario.rol == "vsc":
        return consulta
    if usuario.rol == "empresa":
        return consulta.where(Cliente.empresa_id == usuario.empresa_id)
    if usuario.rol == "cliente":
        return consulta.where(Sucursal.cliente_id == usuario.cliente_id)
    return consulta.where(False)


def usuarios_visibles(usuario: Usuario, incluir_inactivos: bool = False) -> Select:
    consulta = _solo_activos(select(Usuario), Usuario, incluir_inactivos)
    if usuario.rol == "vsc":
        return consulta
    if usuario.rol == "empresa":
        clientes_de_la_empresa = select(Cliente.id).where(Cliente.empresa_id == usuario.empresa_id)
        return consulta.where(
            or_(
                Usuario.empresa_id == usuario.empresa_id,
                Usuario.cliente_id.in_(clientes_de_la_empresa),
            )
        )
    # Un cliente solo se ve a sí mismo.
    return consulta.where(Usuario.id == usuario.id)


def obtener_en_scope(db: Session, usuario: Usuario, modelo, objeto_id: int, consulta: Select, nombre: str):
    """Busca un registro por id y verifica que el usuario tenga acceso.

    - No existe: 404.
    - Existe pero está fuera del scope del usuario: 403 + registro de seguridad.
    """
    objeto = db.get(modelo, objeto_id)
    if objeto is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{nombre} no encontrado")
    if db.scalar(consulta.where(modelo.id == objeto_id)) is None:
        registrar_acceso_denegado(usuario, f"{nombre} {objeto_id}")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"No tienes acceso a este {nombre}")
    return objeto


# ---------- Quién puede EDITAR ----------

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


def requiere_vsc(usuario: Usuario = Depends(get_usuario_actual)) -> Usuario:
    """Dependencia para operaciones reservadas al administrador de plataforma (VSC)."""
    if usuario.rol != "vsc":
        registrar_acceso_denegado(usuario, "operación exclusiva de VSC")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo el administrador VSC puede realizar esta operación",
        )
    return usuario
