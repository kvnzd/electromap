"""Pruebas automáticas de umbrales y motor de alarmas (Etapa 14 — Historia 005).

Cubren: la API de umbrales (crear, validar mínimo/máximo, duplicados, permisos,
listar y desactivar) y el motor (crea la alarma una sola vez, severidad, voltaje bajo
y alto, potencia, histéresis al resolver, umbral desactivado, orden de tiempo dentro
de un envío y aviso por el WebSocket).
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import Alarma, Circuito, Dispositivo, UmbralConfigurado
from app.servicio_mediciones import registrar_mediciones
from tests.conftest import auth

AHORA = datetime(2026, 11, 5, 15, 0, tzinfo=timezone.utc)


def _circuito(db, tablero, codigo="C1"):
    equipo = Dispositivo(tablero_id=tablero.id, numero_serie=f"EQ-{codigo}")
    db.add(equipo); db.flush()
    c = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo=codigo, nombre="Circuito",
                 corriente_automatico=Decimal("16"))
    db.add(c); db.flush()
    return c


def _umbral(db, circuito, tipo, maximo, minimo=None):
    u = UmbralConfigurado(circuito_id=circuito.id, tipo_variable=tipo, valor_umbral=Decimal(str(maximo)),
                          valor_minimo=None if minimo is None else Decimal(str(minimo)))
    db.add(u); db.flush()
    return u


def _medir(db, circuito, segundos=0, avisos=None, **valores):
    fila = {"dispositivo_id": circuito.dispositivo_id, "circuito_id": circuito.id,
            "medido_en": AHORA + timedelta(seconds=segundos), "voltaje_a": 220.0, "corriente_a": 10.0,
            "potencia_activa": 2000.0, **valores}
    notificar = (lambda t, e: avisos.append(e)) if avisos is not None else None
    registrar_mediciones(db, [fila], notificar=notificar)


def _alarmas(db, circuito):
    return db.scalars(select(Alarma).where(Alarma.circuito_id == circuito.id).order_by(Alarma.id)).all()


# ---------- API de umbrales ----------

def test_crear_umbral_de_corriente_y_listarlo(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    c = _circuito(db, ta1)
    editor = escenario["usuarios"]["emp_a"]
    r = cliente_http.post("/umbrales", json={"circuito_id": c.id, "tipo_variable": "corriente", "valor_umbral": 16},
                          headers=auth(editor))
    assert r.status_code == 201
    assert r.json()["valor_umbral"] == 16 and r.json()["valor_minimo"] is None and r.json()["activo"] is True
    # Un cliente de ese tablero puede verlo, pero no crearlo.
    lista = cliente_http.get("/umbrales", params={"tablero_id": ta1.id}, headers=auth(escenario["usuarios"]["cli_a1"]))
    assert [u["tipo_variable"] for u in lista.json()] == ["corriente"]
    r = cliente_http.post("/umbrales", json={"circuito_id": c.id, "tipo_variable": "potencia", "valor_umbral": 3000},
                          headers=auth(escenario["usuarios"]["cli_a1"]))
    assert r.status_code == 403


def test_umbral_de_voltaje_necesita_minimo_menor_que_maximo(cliente_http, db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    h = auth(escenario["usuarios"]["vsc"])
    base = {"circuito_id": c.id, "tipo_variable": "voltaje", "valor_umbral": 236.5}
    assert cliente_http.post("/umbrales", json=base, headers=h).status_code == 400                         # sin mínimo
    assert cliente_http.post("/umbrales", json={**base, "valor_minimo": 240}, headers=h).status_code == 400  # mín ≥ máx
    assert cliente_http.post("/umbrales", json={"circuito_id": c.id, "tipo_variable": "corriente",
                                                "valor_umbral": 16, "valor_minimo": 1}, headers=h).status_code == 400
    r = cliente_http.post("/umbrales", json={**base, "valor_minimo": 203.5}, headers=h)
    assert r.status_code == 201 and r.json()["valor_minimo"] == 203.5
    # El mismo circuito y variable otra vez → 409. Editar el mínimo por encima del máximo → 400.
    assert cliente_http.post("/umbrales", json={**base, "valor_minimo": 200}, headers=h).status_code == 409
    assert cliente_http.patch(f"/umbrales/{r.json()['id']}", json={"valor_minimo": 250}, headers=h).status_code == 400


def test_umbral_de_circuito_ajeno_responde_403(cliente_http, db, escenario):
    ajeno = _circuito(db, escenario["tableros"]["TB1"])
    r = cliente_http.post("/umbrales", json={"circuito_id": ajeno.id, "tipo_variable": "corriente", "valor_umbral": 16},
                          headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 403
    u = _umbral(db, ajeno, "corriente", 16)
    r = cliente_http.patch(f"/umbrales/{u.id}", json={"activo": False}, headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 403


# ---------- Motor de alarmas ----------

def test_corriente_sobre_el_umbral_crea_una_sola_alarma(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    _umbral(db, c, "corriente", 16)
    _medir(db, c, 0, corriente_a=15.9)
    assert _alarmas(db, c) == []
    _medir(db, c, 5, corriente_a=17.0)
    _medir(db, c, 10, corriente_a=17.5)   # sigue alto: no se repite
    [alarma] = _alarmas(db, c)
    assert alarma.tipo == "umbral_corriente" and alarma.severidad == "moderada" and not alarma.resuelto
    assert alarma.valor_medido == Decimal("17.00") and alarma.valor_umbral == Decimal("16.00")
    assert alarma.mensaje == "Corriente 17,0 A en fase A supera el umbral de 16,0 A"
    assert alarma.generado_en == AHORA + timedelta(seconds=5)   # momento de la medición


def test_se_resuelve_sola_con_margen_de_histeresis(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    _umbral(db, c, "corriente", 16)
    _medir(db, c, 0, corriente_a=17.0)
    _medir(db, c, 5, corriente_a=15.9)    # bajo 16 pero sobre 15,68 (margen 2 %): sigue abierta
    assert not _alarmas(db, c)[0].resuelto
    _medir(db, c, 10, corriente_a=15.0)
    [alarma] = _alarmas(db, c)
    assert alarma.resuelto and alarma.resuelto_en == AHORA + timedelta(seconds=10) and alarma.resuelto_por is None


def test_fase_mas_cargada_y_severidad_critica(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    _umbral(db, c, "corriente", 20)
    _medir(db, c, 0, corriente_a=12.0, corriente_b=22.5, corriente_c=14.0)   # 12,5 % sobre el límite
    [alarma] = _alarmas(db, c)
    assert alarma.severidad == "critica" and "fase B" in alarma.mensaje


def test_voltaje_bajo_el_minimo_y_sobre_el_maximo(db, escenario):
    bajo, alto = _circuito(db, escenario["tableros"]["TA1"], "C1"), _circuito(db, escenario["tableros"]["TA1"], "C2")
    _umbral(db, bajo, "voltaje", 236.5, 203.5)
    _umbral(db, alto, "voltaje", 236.5, 203.5)
    _medir(db, bajo, 0, voltaje_a=200.0)
    _medir(db, alto, 0, voltaje_a=240.0)
    [a_bajo], [a_alto] = _alarmas(db, bajo), _alarmas(db, alto)
    assert a_bajo.tipo == "umbral_voltaje" and a_bajo.valor_umbral == Decimal("203.50") and "bajo el mínimo" in a_bajo.mensaje
    assert a_alto.valor_umbral == Decimal("236.50") and "supera el máximo" in a_alto.mensaje
    _medir(db, bajo, 5, voltaje_a=220.0)
    assert _alarmas(db, bajo)[0].resuelto


def test_potencia_en_kw_y_umbral_desactivado(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    u = _umbral(db, c, "potencia", 3000)
    _medir(db, c, 0, potencia_activa=3500.0)
    assert _alarmas(db, c)[0].mensaje == "Potencia 3,5 kW supera el umbral de 3,0 kW"
    u.activo = False; db.flush()
    _medir(db, c, 5, potencia_activa=3600.0)   # sin umbral activo: la alarma se cierra
    assert _alarmas(db, c)[0].resuelto


def test_pico_y_normalidad_en_un_mismo_envio(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    _umbral(db, c, "corriente", 16)
    base = {"dispositivo_id": c.dispositivo_id, "circuito_id": c.id, "voltaje_a": 220.0}
    # Llegan desordenadas: el motor las revisa en orden de tiempo.
    registrar_mediciones(db, [{**base, "medido_en": AHORA + timedelta(minutes=1), "corriente_a": 10.0},
                              {**base, "medido_en": AHORA, "corriente_a": 18.0}])
    [alarma] = _alarmas(db, c)
    assert alarma.resuelto and alarma.generado_en == AHORA and alarma.resuelto_en == AHORA + timedelta(minutes=1)


def test_sin_umbral_no_hay_alarma_y_no_toca_otras_alarmas(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    offline = Alarma(dispositivo_id=c.dispositivo_id, tipo="dispositivo_offline", severidad="critica")
    db.add(offline); db.flush()
    _medir(db, c, 0, corriente_a=99.0)
    assert db.scalars(select(Alarma.tipo).where(Alarma.dispositivo_id == c.dispositivo_id)).all() == ["dispositivo_offline"]
    assert not offline.resuelto


def test_alarma_nueva_se_avisa_despues_de_la_medicion(db, escenario):
    c = _circuito(db, escenario["tableros"]["TA1"])
    _umbral(db, c, "corriente", 16)
    avisos = []
    _medir(db, c, 0, avisos=avisos, corriente_a=17.0)
    assert [e["tipo"] for e in avisos] == ["medicion", "alarma"]
    assert avisos[1]["accion"] == "creada" and avisos[1]["alarma_tipo"] == "umbral_corriente"
    assert avisos[1]["circuito_id"] == c.id
