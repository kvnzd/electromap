"""Preparación de las pruebas que necesitan base de datos.

Usan SOLO la base de pruebas (TEST_DATABASE_URL), nunca la real:
1. Al iniciar, borran y recrean el schema de la base de PRUEBAS con database/schema.sql
   (la copia oficial del schema; así las pruebas usan exactamente la misma estructura).
2. Cada prueba corre dentro de una transacción que se deshace al terminar:
   ningún dato de prueba queda guardado.

Protección: si TEST_DATABASE_URL apunta a la misma base que DATABASE_URL,
las pruebas se detienen sin tocar nada.
"""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.config import a_url_sqlalchemy, settings
from app.db import get_db
from app.main import app
from app.models import Cliente, Empresa, Sucursal, Tablero, Usuario
from app.security import crear_token, hashear_password

SCHEMA_SQL = Path(__file__).resolve().parents[2] / "database" / "schema.sql"


def _misma_base(url_a: str, url_b: str) -> bool:
    a, b = make_url(a_url_sqlalchemy(url_a)), make_url(a_url_sqlalchemy(url_b))
    return (a.host, a.port, a.database) == (b.host, b.port, b.database)


@pytest.fixture(scope="session")
def engine_pruebas():
    if not settings.test_database_url:
        pytest.skip("TEST_DATABASE_URL no está configurada en .env")
    if _misma_base(settings.test_database_url, settings.database_url):
        pytest.exit("PELIGRO: TEST_DATABASE_URL apunta a la base REAL. Pruebas canceladas.", 2)

    engine = create_engine(a_url_sqlalchemy(settings.test_database_url))
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        conn.exec_driver_sql(SCHEMA_SQL.read_text(encoding="utf-8"))
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine_pruebas):
    """Sesión dentro de una transacción que se deshace al final de cada prueba."""
    conn = engine_pruebas.connect()
    trans = conn.begin()
    sesion = Session(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield sesion
    finally:
        sesion.close()
        trans.rollback()
        conn.close()


@pytest.fixture
def cliente_http(db):
    """Cliente HTTP de pruebas: la API usa la sesión de pruebas en vez de la base real."""
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def escenario(db):
    """Dos empresas con sus clientes, sucursales, tableros y usuarios de cada rol.

    Empresa A
      ├─ Cliente A1 ─ Sucursal A1 ─ Tablero TA1
      └─ Cliente A2 ─ Sucursal A2 ─ Tablero TA2
    Empresa B
      └─ Cliente B1 ─ Sucursal B1 ─ Tablero TB1
    """
    pw = hashear_password("ClavePrueba123")

    emp_a, emp_b = Empresa(nombre="Empresa A"), Empresa(nombre="Empresa B")
    db.add_all([emp_a, emp_b]); db.flush()
    cli_a1 = Cliente(empresa_id=emp_a.id, nombre="Cliente A1")
    cli_a2 = Cliente(empresa_id=emp_a.id, nombre="Cliente A2")
    cli_b1 = Cliente(empresa_id=emp_b.id, nombre="Cliente B1")
    db.add_all([cli_a1, cli_a2, cli_b1]); db.flush()
    suc = {c.nombre: Sucursal(cliente_id=c.id, nombre=f"Sucursal {c.nombre[-2:]}") for c in (cli_a1, cli_a2, cli_b1)}
    db.add_all(suc.values()); db.flush()
    tab = {
        "TA1": Tablero(sucursal_id=suc["Cliente A1"].id, codigo="TA1", nombre="Tablero A1"),
        "TA2": Tablero(sucursal_id=suc["Cliente A2"].id, codigo="TA2", nombre="Tablero A2"),
        "TB1": Tablero(sucursal_id=suc["Cliente B1"].id, codigo="TB1", nombre="Tablero B1"),
    }
    db.add_all(tab.values()); db.flush()

    usr = {
        "vsc": Usuario(nombre_usuario="t_vsc", password_hash=pw, rol="vsc", puede_editar=True),
        "emp_a": Usuario(nombre_usuario="t_emp_a", password_hash=pw, rol="empresa", empresa_id=emp_a.id, puede_editar=True),
        "emp_a_lector": Usuario(nombre_usuario="t_emp_a_lector", password_hash=pw, rol="empresa", empresa_id=emp_a.id, puede_editar=False),
        "emp_b": Usuario(nombre_usuario="t_emp_b", password_hash=pw, rol="empresa", empresa_id=emp_b.id, puede_editar=True),
        "cli_a1": Usuario(nombre_usuario="t_cli_a1", password_hash=pw, rol="cliente", cliente_id=cli_a1.id),
        "cli_a2": Usuario(nombre_usuario="t_cli_a2", password_hash=pw, rol="cliente", cliente_id=cli_a2.id),
    }
    db.add_all(usr.values()); db.flush()
    usr["cli_b1_id"] = cli_b1.id  # id de un cliente de la empresa B (para probar accesos cruzados)
    return {"tableros": tab, "usuarios": usr}


def auth(usuario: Usuario) -> dict:
    """Encabezado de autorización con un token válido para el usuario."""
    return {"Authorization": f"Bearer {crear_token(usuario.id)}"}
