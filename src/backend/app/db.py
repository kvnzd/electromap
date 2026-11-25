"""Conexión a la base de datos PostgreSQL.

REGLA DEL PROYECTO: el backend NUNCA crea ni modifica tablas.
No se usa create_all() ni migraciones: el schema se administra solo
desde el proceso de base de datos (ver database/schema.sql).
"""
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

# pool_pre_ping: verifica que la conexión siga viva antes de usarla.
engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    """Entrega una sesión de base de datos por cada petición y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
