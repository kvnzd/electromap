"""Consulta de tableros, filtrada según el scope de cada usuario."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.autorizacion import registrar_acceso_denegado, tableros_visibles
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Tablero, Usuario
from app.schemas import TableroOut

router = APIRouter(prefix="/tableros", tags=["tableros"])


@router.get("", response_model=list[TableroOut])
def listar_tableros(
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Lista solo los tableros que el usuario conectado tiene permitido ver."""
    return db.scalars(tableros_visibles(usuario).order_by(Tablero.id)).all()


@router.get("/{tablero_id}", response_model=TableroOut)
def ver_tablero(
    tablero_id: int,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Devuelve un tablero. Si existe pero está fuera del scope del usuario: 403 + registro."""
    tablero = db.get(Tablero, tablero_id)
    if tablero is None or not tablero.activo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tablero no encontrado")

    visible = db.scalar(tableros_visibles(usuario).where(Tablero.id == tablero_id))
    if visible is None:
        registrar_acceso_denegado(usuario, f"tablero {tablero_id}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes acceso a este tablero",
        )
    return visible
