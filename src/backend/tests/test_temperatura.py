"""Pruebas automáticas de la temperatura estimada del conductor (Etapa 19a).

Cubren: la fórmula (ejemplo del plan, sin carga, sin datos), la fase más cargada,
el estado actual del tablero (con y sin calibre asignado) y el aviso en tiempo real.
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timezone
from decimal import Decimal

from app.models import CalibreCable, Circuito, Dispositivo
from app.servicio_mediciones import registrar_mediciones
from app.temperatura import corriente_mayor, estimar_temperatura
from tests.conftest import auth

AHORA = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)


def test_formula_de_la_temperatura_estimada():
    assert estimar_temperatura(20, 25, 30, 70) == 55.6      # ejemplo del plan
    assert estimar_temperatura(0, 25, 30, 70) == 30.0       # sin carga = temperatura ambiente
    assert estimar_temperatura(25, 25, 30, 70) == 70.0      # a la ampacidad = máxima de la aislación
    assert estimar_temperatura(None, 25) is None            # sin medición
    assert estimar_temperatura(20, None) is None            # sin calibre


def test_usa_la_fase_mas_cargada():
    assert corriente_mayor({"corriente_a": 10.0, "corriente_b": 14.5, "corriente_c": None}) == 14.5
    assert corriente_mayor({"corriente_a": None}) is None


def _circuitos(db, tablero):
    db.merge(CalibreCable(calibre_mm2=Decimal("2.5"), corriente_maxima=Decimal("20")))
    equipo = Dispositivo(tablero_id=tablero.id, numero_serie="EQ-T")
    db.add(equipo); db.flush()
    con = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo="C1", nombre="Con calibre",
                   calibre_cable_mm2=Decimal("2.5"))
    sin = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo="C2", nombre="Sin calibre")
    db.add_all([con, sin]); db.flush()
    return con, sin


def _fila(circuito, corriente):
    return {"dispositivo_id": circuito.dispositivo_id, "circuito_id": circuito.id, "medido_en": AHORA,
            "voltaje_a": 220.0, "corriente_a": corriente}


def test_estado_actual_entrega_la_temperatura_estimada(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    con, sin = _circuitos(db, ta1)
    registrar_mediciones(db, [_fila(con, 10.0), _fila(sin, 10.0)])
    datos = cliente_http.get("/mediciones/estado-actual", params={"tablero_id": ta1.id},
                             headers=auth(escenario["usuarios"]["cli_a1"])).json()
    assert datos["temperatura_ambiente"] == 30.0 and datos["temperatura_max_aislacion"] == 70.0
    por_codigo = {c["codigo"]: c for c in datos["circuitos"]}
    assert por_codigo["C1"]["calibre_cable_mm2"] == 2.5 and por_codigo["C1"]["ampacidad_cable"] == 20.0
    assert por_codigo["C1"]["ultima"]["temperatura_conductor"] == 40.0   # 30 + 40·(10/20)²
    assert por_codigo["C2"]["ampacidad_cable"] is None
    assert por_codigo["C2"]["ultima"]["temperatura_conductor"] is None


def test_el_aviso_en_vivo_trae_la_temperatura(db, escenario):
    con, sin = _circuitos(db, escenario["tableros"]["TA1"])
    avisos = []
    registrar_mediciones(db, [_fila(con, 20.0), _fila(sin, 20.0)], notificar=lambda t, e: avisos.append(e))
    temperatura = {e["circuito_id"]: e["temperatura_conductor"] for e in avisos if e["tipo"] == "medicion"}
    assert temperatura == {con.id: 70.0, sin.id: None}
