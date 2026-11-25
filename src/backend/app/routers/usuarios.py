"""Administración de usuarios y asignación de niveles de acceso.

Reglas al CREAR un usuario (el nivel de acceso queda fijado desde su creación):
- rol 'vsc'     : solo lo crea otro VSC. Sin empresa ni cliente.
- rol 'empresa' : VSC indica la empresa; un usuario empresa solo crea usuarios
                  de SU empresa (se asigna automáticamente).
- rol 'cliente' : el cliente debe estar dentro del scope de quien lo crea.
                  Un cliente NUNCA puede editar.
El rol y el scope no se cambian después; para eso se desactiva y se crea otro.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.autorizacion import (
    clientes_visibles,
    empresas_visibles,
    obtener_en_scope,
    registrar_acceso_denegado,
    registrar_auditoria,
    requiere_editor,
    usuarios_visibles,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Cliente, Empresa, Usuario
from app.schemas import UsuarioCrear, UsuarioEditar, UsuarioOut
from app.security import hashear_password
from app.utils import guardar

router = APIRouter(prefix="/usuarios", tags=["administración: usuarios"])

_NOMBRE_REPETIDO = "Ya existe un usuario con ese nombre"


def _prohibido(usuario: Usuario, recurso: str, mensaje: str):
    registrar_acceso_denegado(usuario, recurso)
    raise HTTPException(status.HTTP_403_FORBIDDEN, mensaje)


@router.get("", response_model=list[UsuarioOut])
def listar_usuarios(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """VSC ve todos; empresa ve los de su empresa y de sus clientes; cliente solo se ve a sí mismo."""
    return db.scalars(usuarios_visibles(usuario, incluir_inactivos).order_by(Usuario.id)).all()


@router.get("/{usuario_id}", response_model=UsuarioOut)
def ver_usuario(usuario_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    return obtener_en_scope(db, usuario, Usuario, usuario_id, usuarios_visibles(usuario, True), "usuario")


@router.post("", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED)
def crear_usuario(datos: UsuarioCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    empresa_id = cliente_id = None
    puede_editar = datos.puede_editar

    if datos.rol == "vsc":
        if usuario.rol != "vsc":
            _prohibido(usuario, "crear usuario vsc", "Solo VSC puede crear usuarios VSC")
        if datos.empresa_id or datos.cliente_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un usuario VSC no pertenece a empresa ni cliente")
        puede_editar = True

    elif datos.rol == "empresa":
        if datos.cliente_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un usuario empresa no lleva cliente_id")
        if usuario.rol == "empresa":
            if datos.empresa_id not in (None, usuario.empresa_id):
                _prohibido(usuario, f"crear usuario en empresa {datos.empresa_id}",
                           "Solo puedes crear usuarios de tu propia empresa")
            empresa_id = usuario.empresa_id
        else:  # vsc
            if datos.empresa_id is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Debes indicar empresa_id")
            empresa_id = datos.empresa_id
        obtener_en_scope(db, usuario, Empresa, empresa_id, empresas_visibles(usuario), "empresa")

    else:  # cliente
        if datos.empresa_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un usuario cliente no lleva empresa_id")
        if datos.cliente_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Debes indicar cliente_id")
        if datos.puede_editar:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un usuario cliente nunca puede editar")
        obtener_en_scope(db, usuario, Cliente, datos.cliente_id, clientes_visibles(usuario), "cliente")
        cliente_id = datos.cliente_id
        puede_editar = False

    nuevo = Usuario(
        nombre_usuario=datos.nombre_usuario,
        password_hash=hashear_password(datos.password),
        rol=datos.rol,
        empresa_id=empresa_id,
        cliente_id=cliente_id,
        puede_editar=puede_editar,
    )
    db.add(nuevo)
    guardar(db, nuevo, _NOMBRE_REPETIDO)
    registrar_auditoria(
        usuario,
        f"CREA usuario id={nuevo.id} nombre={nuevo.nombre_usuario!r} rol={nuevo.rol} "
        f"empresa_id={empresa_id} cliente_id={cliente_id} puede_editar={puede_editar}",
    )
    return nuevo


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def editar_usuario(
    usuario_id: int,
    datos: UsuarioEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    """Cambiar permiso de edición, desactivar/reactivar o reiniciar la contraseña."""
    objetivo = obtener_en_scope(db, usuario, Usuario, usuario_id, usuarios_visibles(usuario, True), "usuario")
    cambios = datos.model_dump(exclude_unset=True)

    if objetivo.id == usuario.id and cambios.get("activo") is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivar tu propia cuenta")
    if objetivo.rol == "cliente" and cambios.get("puede_editar"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Un usuario cliente nunca puede editar")

    if "puede_editar" in cambios and objetivo.rol != "vsc":
        objetivo.puede_editar = cambios["puede_editar"]
    if "activo" in cambios:
        objetivo.activo = cambios["activo"]
    if cambios.get("password"):
        objetivo.password_hash = hashear_password(cambios["password"])

    guardar(db, objetivo)
    # La contraseña nunca se escribe en el registro: solo que fue cambiada.
    registrar_auditoria(usuario, f"EDITA usuario id={objetivo.id} cambios={sorted(cambios)}")
    return objetivo
