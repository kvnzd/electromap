"""Rutas de verificación del sistema. Solo lectura (SELECT): no modifican nada."""
from fastapi import APIRouter, Depends
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.models import Base

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


@router.get("/health/schema")
def schema_check():
    """Compara los modelos del código (models.py) contra el schema REAL de la base de datos.

    - faltan_en_bbdd: columnas que el código espera y NO existen -> hay que ir al chat de BBDD.
    - no_mapeadas_en_codigo: columnas que existen en la BBDD pero el código no conoce.
    Si "ok" es true, el código y la base de datos calzan.
    """
    inspector = inspect(engine)
    tablas_bbdd = set(inspector.get_table_names())
    resultado = {"ok": True, "tablas_revisadas": 0, "diferencias": {}}

    for tabla in Base.metadata.sorted_tables:
        resultado["tablas_revisadas"] += 1
        if tabla.name not in tablas_bbdd:
            resultado["ok"] = False
            resultado["diferencias"][tabla.name] = "LA TABLA NO EXISTE EN LA BBDD"
            continue

        cols_bbdd = {c["name"] for c in inspector.get_columns(tabla.name)}
        cols_codigo = {c.name for c in tabla.columns}
        faltan = sorted(cols_codigo - cols_bbdd)
        sobran = sorted(cols_bbdd - cols_codigo)
        if faltan or sobran:
            resultado["ok"] = False
            resultado["diferencias"][tabla.name] = {
                "faltan_en_bbdd": faltan,
                "no_mapeadas_en_codigo": sobran,
            }

    return resultado
