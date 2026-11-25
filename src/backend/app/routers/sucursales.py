"""Administración de sucursales (ubicaciones de un cliente)."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.autorizacion import (
    clientes_visibles,
    obtener_en_scope,
    registrar_auditoria,
    requiere_editor,
    sucursales_visibles,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Cliente, Sucursal, Usuario
from app.schemas import SucursalCrear, SucursalEditar, SucursalOut
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/sucursales", tags=["administración: sucursales"])


@router.get("", response_model=list[SucursalOut])
def listar_sucursales(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    return db.scalars(sucursales_visibles(usuario, incluir_inactivos).order_by(Sucursal.id)).all()


@router.get("/{sucursal_id}", response_model=SucursalOut)
def ver_sucursal(sucursal_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    return obtener_en_scope(db, usuario, Sucursal, sucursal_id, sucursales_visibles(usuario, True), "sucursal")


@router.post("", response_model=SucursalOut, status_code=status.HTTP_201_CREATED)
def crear_sucursal(datos: SucursalCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    """El cliente debe estar dentro del scope de quien crea la sucursal."""
    obtener_en_scope(db, usuario, Cliente, datos.cliente_id, clientes_visibles(usuario), "cliente")
    sucursal = Sucursal(**datos.model_dump())
    db.add(sucursal)
    guardar(db, sucursal)
    registrar_auditoria(usuario, f"CREA sucursal id={sucursal.id} cliente_id={sucursal.cliente_id}")
    return sucursal


@router.patch("/{sucursal_id}", response_model=SucursalOut)
def editar_sucursal(
    sucursal_id: int,
    datos: SucursalEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    sucursal = obtener_en_scope(db, usuario, Sucursal, sucursal_id, sucursales_visibles(usuario, True), "sucursal")
    cambios = aplicar_cambios(sucursal, datos)
    guardar(db, sucursal)
    registrar_auditoria(usuario, f"EDITA sucursal id={sucursal.id} cambios={sorted(cambios)}")
    return sucursal
