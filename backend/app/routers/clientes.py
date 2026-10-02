"""Administración de clientes finales (pertenecen a una empresa)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.autorizacion import (
    clientes_visibles,
    empresas_visibles,
    obtener_en_scope,
    registrar_acceso_denegado,
    registrar_auditoria,
    requiere_editor,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Cliente, Empresa, Usuario
from app.schemas import ClienteCrear, ClienteEditar, ClienteOut
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/clientes", tags=["administración: clientes"])


@router.get("", response_model=list[ClienteOut])
def listar_clientes(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    return db.scalars(clientes_visibles(usuario, incluir_inactivos).order_by(Cliente.id)).all()


@router.get("/{cliente_id}", response_model=ClienteOut)
def ver_cliente(cliente_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    return obtener_en_scope(db, usuario, Cliente, cliente_id, clientes_visibles(usuario, True), "cliente")


@router.post("", response_model=ClienteOut, status_code=status.HTTP_201_CREATED)
def crear_cliente(datos: ClienteCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    """VSC indica la empresa. Un usuario empresa crea clientes SOLO en su propia empresa
    (se asigna automáticamente)."""
    if usuario.rol == "empresa":
        if datos.empresa_id not in (None, usuario.empresa_id):
            registrar_acceso_denegado(usuario, f"crear cliente en empresa {datos.empresa_id}")
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Solo puedes crear clientes en tu propia empresa")
        empresa_id = usuario.empresa_id
    else:  # vsc
        if datos.empresa_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Debes indicar empresa_id")
        empresa_id = datos.empresa_id

    # La empresa debe existir y estar activa.
    obtener_en_scope(db, usuario, Empresa, empresa_id, empresas_visibles(usuario), "empresa")

    cliente = Cliente(empresa_id=empresa_id, nombre=datos.nombre)
    db.add(cliente)
    guardar(db, cliente)
    registrar_auditoria(usuario, f"CREA cliente id={cliente.id} empresa_id={empresa_id}")
    return cliente


@router.patch("/{cliente_id}", response_model=ClienteOut)
def editar_cliente(
    cliente_id: int,
    datos: ClienteEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    cliente = obtener_en_scope(db, usuario, Cliente, cliente_id, clientes_visibles(usuario, True), "cliente")
    cambios = aplicar_cambios(cliente, datos)
    guardar(db, cliente)
    registrar_auditoria(usuario, f"EDITA cliente id={cliente.id} cambios={sorted(cambios)}")
    return cliente
