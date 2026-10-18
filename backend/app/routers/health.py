"""Ruta de verificación del sistema. Solo lectura (SELECT)."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    """Confirma que la API está viva y que la base de datos responde."""
    version = db.execute(text("SELECT version()")).scalar_one()
    tablas = db.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
    ).scalar_one()
    return {
        "status": "ok",
        "base_de_datos": version.split(",")[0],
        "tablas_en_bbdd": tablas,
    }
