"""Pruebas automáticas del historial de mediciones y del simulador (Etapa 18).

Cubren: permisos por ámbito (403/404), validación del rango de fechas (400),
promedio por intervalos según el rango, resumen por circuito, aviso sin datos,
y que el simulador solo opera en tableros DEMO y no duplica mediciones.
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.models import Circuito, Dispositivo, Medicion, Tablero
from scripts.simular_mediciones import borrar, simular
from tests.conftest import auth

INICIO = datetime(2026, 11, 1, 12, 0, tzinfo=timezone.utc)


def _circuito(db, tablero, codigo="C1", nombre="Alumbrado"):
    equipo = Dispositivo(tablero_id=tablero.id)
    db.add(equipo); db.flush()
    c = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo=codigo, nombre=nombre)
    db.add(c); db.flush()
    return c


def _mediciones(db, circuito, minutos, corriente=lambda i: 10, energia_inicial=100.0):
    """Una medición por minuto desde INICIO; energía acumulada que sube 0,1 kWh por minuto."""
    for i in range(minutos):
        db.add(Medicion(
            dispositivo_id=circuito.dispositivo_id, circuito_id=circuito.id,
            medido_en=INICIO + timedelta(minutes=i), voltaje_a=Decimal("220"),
            corriente_a=Decimal(str(corriente(i))), potencia_activa=Decimal("2000"),
            energia_kwh=Decimal(str(round(energia_inicial + i * 0.1, 3))),
        ))
    db.flush()


def _pedir(cliente_http, usuario, tablero, desde, hasta):
    return cliente_http.get("/mediciones/historial", headers=auth(usuario), params={
        "tablero_id": tablero.id, "desde": desde.isoformat(), "hasta": hasta.isoformat()})


# ---------- Permisos y validaciones ----------

def test_cliente_no_ve_historial_de_otro_cliente(cliente_http, escenario):
    r = _pedir(cliente_http, escenario["usuarios"]["cli_a1"], escenario["tableros"]["TA2"],
               INICIO, INICIO + timedelta(hours=1))
    assert r.status_code == 403


def test_tablero_inexistente_responde_404(cliente_http, escenario):
    r = cliente_http.get("/mediciones/historial", headers=auth(escenario["usuarios"]["vsc"]), params={
        "tablero_id": 999999, "desde": INICIO.isoformat(), "hasta": (INICIO + timedelta(hours=1)).isoformat()})
    assert r.status_code == 404


@pytest.mark.parametrize("duracion", [timedelta(0), timedelta(hours=-1), timedelta(days=32)])
def test_rango_invalido_responde_400(cliente_http, escenario, duracion):
    r = _pedir(cliente_http, escenario["usuarios"]["vsc"], escenario["tableros"]["TA1"],
               INICIO, INICIO + duracion)
    assert r.status_code == 400


# ---------- Contenido ----------

def test_rango_corto_entrega_un_punto_por_minuto(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    circuito = _circuito(db, ta1)
    _mediciones(db, circuito, minutos=120)
    r = _pedir(cliente_http, escenario["usuarios"]["cli_a1"], ta1, INICIO, INICIO + timedelta(hours=2))
    assert r.status_code == 200
    datos = r.json()
    assert datos["hay_datos"] is True and datos["intervalo_segundos"] == 60
    [c] = datos["circuitos"]
    assert c["codigo"] == "C1" and len(c["puntos"]) == 120
    assert c["puntos"][0]["voltaje_a"] == 220 and c["puntos"][0]["voltaje_b"] is None  # monofásico


def test_rango_largo_promedia_por_intervalos(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    circuito = _circuito(db, ta1)
    # 10 minutos: corriente 0,2,4,...,18 → los primeros 5 min (un bloque) promedian 4.
    _mediciones(db, circuito, minutos=10, corriente=lambda i: 2 * i)
    r = _pedir(cliente_http, escenario["usuarios"]["vsc"], ta1, INICIO, INICIO + timedelta(days=1))
    datos = r.json()
    assert datos["intervalo_segundos"] == 300
    puntos = datos["circuitos"][0]["puntos"]
    assert len(puntos) == 2
    assert puntos[0]["corriente_a"] == 4.0 and puntos[1]["corriente_a"] == 14.0


def test_resumen_por_circuito(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    circuito = _circuito(db, ta1)
    _mediciones(db, circuito, minutos=60, corriente=lambda i: 5 + i % 7)
    r = _pedir(cliente_http, escenario["usuarios"]["vsc"], ta1, INICIO, INICIO + timedelta(hours=1))
    resumen = r.json()["circuitos"][0]["resumen"]
    assert resumen["corriente_max"] == 11.0
    assert resumen["potencia_max"] == 2000.0
    assert resumen["energia_kwh"] == 5.9  # (59 − 0) × 0,1 kWh


def test_sin_mediciones_en_el_rango_avisa_sin_datos(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    circuito = _circuito(db, ta1)
    _mediciones(db, circuito, minutos=10)
    otro_dia = INICIO + timedelta(days=5)
    datos = _pedir(cliente_http, escenario["usuarios"]["vsc"], ta1, otro_dia, otro_dia + timedelta(hours=1)).json()
    assert datos["hay_datos"] is False
    assert datos["circuitos"][0]["puntos"] == []


def test_solo_incluye_circuitos_del_tablero_pedido(cliente_http, db, escenario):
    tab = escenario["tableros"]
    propio, ajeno = _circuito(db, tab["TA1"], "P1"), _circuito(db, tab["TA2"], "X1")
    _mediciones(db, propio, minutos=5)
    _mediciones(db, ajeno, minutos=5)
    datos = _pedir(cliente_http, escenario["usuarios"]["vsc"], tab["TA1"], INICIO, INICIO + timedelta(hours=1)).json()
    assert [c["codigo"] for c in datos["circuitos"]] == ["P1"]


# ---------- Simulador ----------

def test_simulador_solo_funciona_en_tableros_demo(db, escenario):
    _circuito(db, escenario["tableros"]["TA1"])
    with pytest.raises(ValueError, match="DEMO"):
        simular(db, escenario["tableros"]["TA1"].id, dias=1)


def test_simulador_carga_sin_duplicar_y_borra(db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    demo = Tablero(sucursal_id=ta1.sucursal_id, codigo="DEMO-01", nombre="Demo")
    db.add(demo); db.flush()
    _circuito(db, demo, "C1", "Alumbrado")
    _circuito(db, demo, "C2-TRI", "Motor trifásico")
    ahora = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)

    assert simular(db, demo.id, dias=1, cada_minutos=10, ahora=ahora) == 2 * 144  # 2 circuitos × 144
    assert simular(db, demo.id, dias=1, cada_minutos=10, ahora=ahora) == 0        # repetir no duplica

    trifasico = db.scalar(select(Medicion).join(Circuito).where(Circuito.codigo == "C2-TRI").limit(1))
    assert trifasico.corriente_c is not None
    monofasico = db.scalar(select(Medicion).join(Circuito).where(Circuito.codigo == "C1").limit(1))
    assert monofasico.corriente_b is None

    assert borrar(db, demo.id) == 288
    assert db.scalar(select(func.count()).select_from(Medicion)) == 0