"""Tableros: consulta filtrada por scope y administración."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.autorizacion import (
    obtener_en_scope,
    registrar_auditoria,
    requiere_editor,
    sucursales_visibles,
    tableros_visibles,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Sucursal, Tablero, Usuario
from app.schemas import TableroCrear, TableroEditar, TableroOut
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/tableros", tags=["tableros"])

_CODIGO_REPETIDO = "Ya existe un tablero con ese código en la sucursal"


@router.get("", response_model=list[TableroOut])
def listar_tableros(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Lista solo los tableros que el usuario conectado tiene permitido ver."""
    return db.scalars(tableros_visibles(usuario, incluir_inactivos).order_by(Tablero.id)).all()


@router.get("/{tablero_id}", response_model=TableroOut)
def ver_tablero(
    tablero_id: int,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Devuelve un tablero activo. Si existe pero está fuera del scope del usuario: 403 + registro."""
    tablero = obtener_en_scope(db, usuario, Tablero, tablero_id, tableros_visibles(usuario, True), "tablero")
    if not tablero.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="tablero no encontrado")
    return tablero


@router.post("", response_model=TableroOut, status_code=status.HTTP_201_CREATED)
def crear_tablero(datos: TableroCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    """La sucursal debe estar dentro del scope de quien crea el tablero."""
    obtener_en_scope(db, usuario, Sucursal, datos.sucursal_id, sucursales_visibles(usuario), "sucursal")
    tablero = Tablero(**datos.model_dump())
    db.add(tablero)
    guardar(db, tablero, _CODIGO_REPETIDO)
    registrar_auditoria(usuario, f"CREA tablero id={tablero.id} codigo={tablero.codigo!r}")
    return tablero


@router.patch("/{tablero_id}", response_model=TableroOut)
def editar_tablero(
    tablero_id: int,
    datos: TableroEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    tablero = obtener_en_scope(db, usuario, Tablero, tablero_id, tableros_visibles(usuario, True), "tablero")
    cambios = aplicar_cambios(tablero, datos)
    guardar(db, tablero, _CODIGO_REPETIDO)
    registrar_auditoria(usuario, f"EDITA tablero id={tablero.id} cambios={sorted(cambios)}")
    return tablero
