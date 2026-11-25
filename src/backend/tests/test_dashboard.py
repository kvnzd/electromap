"""Pruebas automáticas del dashboard en tiempo real (Etapa 17).

Cubren: el servicio que guarda y avisa mediciones (sin duplicar, solo al tablero
correcto), el estado actual de un tablero (última medición, equipos, alarmas abiertas,
permisos) y el simulador en vivo (solo DEMO, una medición por circuito, energía creciente,
y que el aviso llega por el WebSocket).
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Alarma, Circuito, Dispositivo, Medicion, Tablero
from app.security import crear_token
from app.servicio_mediciones import registrar_mediciones
from app.simulador_vivo import un_envio
from app.tiempo_real import canal
from tests.conftest import auth

AHORA = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)


def _circuito(db, tablero, codigo="C1", nombre="Alumbrado", equipo=None):
    if equipo is None:
        equipo = Dispositivo(tablero_id=tablero.id, numero_serie=f"EQ-{codigo}")
        db.add(equipo); db.flush()
    c = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo=codigo, nombre=nombre,
                 corriente_automatico=Decimal("20"))
    db.add(c); db.flush()
    return c


def _fila(circuito, momento, corriente=10.0):
    return {"dispositivo_id": circuito.dispositivo_id, "circuito_id": circuito.id, "medido_en": momento,
            "voltaje_a": 220.0, "corriente_a": corriente, "potencia_activa": 2000.0, "energia_kwh": 1.5}


# ---------- Servicio: guardar y avisar ----------

def test_registrar_guarda_avisa_y_no_duplica(db, escenario):
    tab = escenario["tableros"]
    c1, c2 = _circuito(db, tab["TA1"]), _circuito(db, tab["TA2"], "X1")
    avisos = []
    nuevas = registrar_mediciones(db, [_fila(c1, AHORA), _fila(c2, AHORA)],
                                  notificar=lambda tablero, evento: avisos.append((tablero, evento)))
    assert nuevas == 2
    # Cada aviso va al tablero de su circuito, con los valores medidos.
    assert {(t, e["circuito_id"]) for t, e in avisos} == {(tab["TA1"].id, c1.id), (tab["TA2"].id, c2.id)}
    assert avisos[0][1]["tipo"] == "medicion" and avisos[0][1]["corriente_a"] == 10.0

    # La misma medición otra vez: no se guarda ni se avisa.
    avisos.clear()
    assert registrar_mediciones(db, [_fila(c1, AHORA)], notificar=lambda t, e: avisos.append(e)) == 0
    assert avisos == []


# ---------- Estado actual del tablero ----------

def test_estado_actual_entrega_la_ultima_medicion_de_cada_circuito(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    con_datos = _circuito(db, ta1, "C1")
    _circuito(db, ta1, "C2")  # circuito sin mediciones
    registrar_mediciones(db, [_fila(con_datos, AHORA - timedelta(minutes=1), 5.0),
                              _fila(con_datos, AHORA, 7.5)])
    r = cliente_http.get("/mediciones/estado-actual", params={"tablero_id": ta1.id},
                         headers=auth(escenario["usuarios"]["cli_a1"]))
    assert r.status_code == 200
    datos = r.json()
    por_codigo = {c["codigo"]: c for c in datos["circuitos"]}
    assert por_codigo["C1"]["ultima"]["corriente_a"] == 7.5           # la más reciente
    assert por_codigo["C2"]["ultima"] is None                          # aún sin mediciones
    assert {e["numero_serie"] for e in datos["equipos"]} == {"EQ-C1", "EQ-C2"}


def test_estado_actual_incluye_solo_alarmas_abiertas_del_tablero(cliente_http, db, escenario):
    tab = escenario["tableros"]
    propio, ajeno = _circuito(db, tab["TA1"]), _circuito(db, tab["TA2"], "X1")
    db.add_all([
        Alarma(dispositivo_id=propio.dispositivo_id, tipo="dispositivo_offline", severidad="critica", mensaje="abierta"),
        Alarma(dispositivo_id=propio.dispositivo_id, tipo="dispositivo_offline", severidad="critica",
               mensaje="resuelta", resuelto=True),
        Alarma(dispositivo_id=ajeno.dispositivo_id, tipo="dispositivo_offline", severidad="critica", mensaje="ajena"),
    ]); db.flush()
    datos = cliente_http.get("/mediciones/estado-actual", params={"tablero_id": tab["TA1"].id},
                             headers=auth(escenario["usuarios"]["vsc"])).json()
    assert [a["mensaje"] for a in datos["alarmas_abiertas"]] == ["abierta"]


def test_estado_actual_de_tablero_ajeno_responde_403(cliente_http, escenario):
    r = cliente_http.get("/mediciones/estado-actual", params={"tablero_id": escenario["tableros"]["TA2"].id},
                         headers=auth(escenario["usuarios"]["cli_a1"]))
    assert r.status_code == 403


# ---------- Simulador en vivo ----------

def _tablero_demo(db, escenario):
    demo = Tablero(sucursal_id=escenario["tableros"]["TA1"].sucursal_id, codigo="DEMO-01", nombre="Demo")
    db.add(demo); db.flush()
    equipo = Dispositivo(tablero_id=demo.id, numero_serie="SIM")
    db.add(equipo); db.flush()
    _circuito(db, demo, "C1", "Alumbrado", equipo)
    _circuito(db, demo, "C2-TRI", "Motor trifásico", equipo)
    return demo, equipo


def test_simulador_en_vivo_solo_en_tableros_demo(db, escenario):
    _circuito(db, escenario["tableros"]["TA1"])
    with pytest.raises(ValueError, match="DEMO"):
        un_envio(db, escenario["tableros"]["TA1"].id, AHORA)


def test_simulador_en_vivo_agrega_una_medicion_por_circuito(db, escenario):
    demo, equipo = _tablero_demo(db, escenario)
    assert un_envio(db, demo.id, AHORA) == 2
    assert un_envio(db, demo.id, AHORA + timedelta(seconds=5)) == 2
    assert db.scalar(select(func.count()).select_from(Medicion)) == 4
    db.refresh(equipo)
    assert equipo.ultima_comunicacion == AHORA + timedelta(seconds=5)   # como un envío real
    energias = db.scalars(select(Medicion.energia_kwh).join(Circuito).where(Circuito.codigo == "C1")
                          .order_by(Medicion.medido_en)).all()
    assert energias[1] > energias[0]                                     # el contador sigue subiendo


def test_medicion_simulada_llega_por_el_websocket(cliente_http, db, escenario):
    demo, _ = _tablero_demo(db, escenario)
    with cliente_http.websocket_connect(f"/ws/tableros/{demo.id}") as ws:
        ws.send_json({"token": crear_token(escenario["usuarios"]["vsc"].id)})
        ws.receive_json()  # conectado
        un_envio(db, demo.id, AHORA, notificar=canal.publicar_desde_hilo)
        eventos = [ws.receive_json(), ws.receive_json()]
    assert {e["tipo"] for e in eventos} == {"medicion"}
    trifasico = next(e for e in eventos if e["corriente_c"] is not None)
    assert trifasico["corriente_a"] is not None and trifasico["corriente_b"] is not None
