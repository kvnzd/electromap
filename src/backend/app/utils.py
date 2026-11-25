"""Funciones de apoyo para las rutas de administración."""
from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def aplicar_cambios(objeto, datos: BaseModel) -> dict:
    """Copia al objeto SOLO los campos que vinieron en la petición (edición parcial)."""
    cambios = datos.model_dump(exclude_unset=True)
    for campo, valor in cambios.items():
        setattr(objeto, campo, valor)
    return cambios


def guardar(db: Session, objeto, mensaje_conflicto: str = "El registro ya existe"):
    """Confirma los cambios. Si chocan con una restricción de la BBDD (ej. código repetido) responde 409."""
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=mensaje_conflicto)
    db.refresh(objeto)
    return objeto
