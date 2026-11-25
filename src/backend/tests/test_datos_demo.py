"""Pruebas de los datos de demostración para Docker (Etapa 22).

Cubren: crea DEMO-01 completo (circuitos con calibre, umbrales, calibres e historial),
no duplica si se ejecuta dos veces y se niega a cargar en una base con otras empresas.
Ejecutar desde backend/:  pytest
"""
import pytest
from sqlalchemy import func, select

from app.models import CalibreCable, Circuito, Medicion, Tablero, UmbralConfigurado
from scripts.datos_demo import cargar


def test_crea_el_tablero_de_demostracion_completo(db):
    tablero_id, creado = cargar(db)
    assert creado and db.get(Tablero, tablero_id).codigo == "DEMO-01"
    circuitos = db.scalars(select(Circuito).where(Circuito.tablero_id == tablero_id).order_by(Circuito.codigo)).all()
    assert [(c.codigo, float(c.calibre_cable_mm2)) for c in circuitos] == [("C1", 2.5), ("C2", 2.5), ("C3-TRI", 6.0)]
    assert db.scalar(select(func.count()).select_from(CalibreCable)) == 11
    assert db.scalar(select(func.count()).select_from(UmbralConfigurado)) == 4
    # 1 día de historial, una medición cada 5 minutos por circuito.
    assert db.scalar(select(func.count()).select_from(Medicion)) == 3 * 288


def test_no_duplica_si_se_ejecuta_otra_vez(db):
    primero, _ = cargar(db)
    segundo, creado = cargar(db)
    assert segundo == primero and creado is False
    assert db.scalar(select(func.count()).select_from(Tablero)) == 1


def test_no_carga_en_una_base_con_otras_empresas(db, escenario):
    with pytest.raises(SystemExit, match="base ya tiene empresas"):
        cargar(db)
    tablero_id, creado = cargar(db, forzar=True)
    assert creado and db.get(Tablero, tablero_id).codigo == "DEMO-01"