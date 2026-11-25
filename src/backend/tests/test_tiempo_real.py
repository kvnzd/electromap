"""Pruebas automáticas del canal en tiempo real (Etapa 16).

Cubren: el WebSocket exige sesión válida (4401) y acceso al tablero (4403),
un usuario con acceso queda suscrito, cada evento llega SOLO a quienes miran
ese tablero (aislamiento entre clientes), y las alarmas del vigilante se avisan.
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone

import pytest
from starlette.websockets import WebSocketDisconnect

from app.models import Dispositivo
from app.routers.tiempo_real import NO_AUTENTICADO, SIN_ACCESO
from app.security import crear_token, generar_clave_ingesta, hashear_clave_ingesta
from app.tiempo_real import canal
from app.vigilante import revisar_equipos


def _url(tablero):
    return f"/ws/tableros/{tablero.id}"


def _equipo(db, tablero, ultima=None):
    """Equipo en el tablero, con su clave en texto plano para enviar a /ingesta."""
    clave = generar_clave_ingesta()
    d = Dispositivo(tablero_id=tablero.id, token_ingesta=hashear_clave_ingesta(clave),
                    ultima_comunicacion=ultima)
    db.add(d); db.flush()
    return d, clave


def _codigo_de_cierre(ws) -> int:
    with pytest.raises(WebSocketDisconnect) as cierre:
        ws.receive_json()
    return cierre.value.code


# ---------- Quién puede conectarse ----------

def test_token_invalido_cierra_con_4401(cliente_http, escenario):
    with cliente_http.websocket_connect(_url(escenario["tableros"]["TA1"])) as ws:
        ws.send_json({"token": "inventado"})
        assert _codigo_de_cierre(ws) == NO_AUTENTICADO


def test_primer_mensaje_sin_token_cierra_con_4401(cliente_http, escenario):
    with cliente_http.websocket_connect(_url(escenario["tableros"]["TA1"])) as ws:
        ws.send_json({"hola": "mundo"})
        assert _codigo_de_cierre(ws) == NO_AUTENTICADO


def test_cliente_no_puede_mirar_tablero_de_otro_cliente(cliente_http, escenario):
    cli_a1 = escenario["usuarios"]["cli_a1"]
    with cliente_http.websocket_connect(_url(escenario["tableros"]["TA2"])) as ws:
        ws.send_json({"token": crear_token(cli_a1.id)})
        assert _codigo_de_cierre(ws) == SIN_ACCESO


def test_empresa_no_puede_mirar_tablero_de_otra_empresa(cliente_http, escenario):
    emp_a = escenario["usuarios"]["emp_a"]
    with cliente_http.websocket_connect(_url(escenario["tableros"]["TB1"])) as ws:
        ws.send_json({"token": crear_token(emp_a.id)})
        assert _codigo_de_cierre(ws) == SIN_ACCESO


def test_usuario_con_acceso_queda_suscrito(cliente_http, escenario):
    ta1, cli_a1 = escenario["tableros"]["TA1"], escenario["usuarios"]["cli_a1"]
    with cliente_http.websocket_connect(_url(ta1)) as ws:
        ws.send_json({"token": crear_token(cli_a1.id)})
        assert ws.receive_json() == {"tipo": "conectado", "tablero_id": ta1.id}
        assert canal.cantidad(ta1.id) == 1
    # Al cerrar el navegador, deja de estar suscrito.
    assert canal.cantidad(ta1.id) == 0


# ---------- Qué recibe cada uno ----------

def test_cada_tablero_recibe_solo_sus_eventos(cliente_http, db, escenario):
    tab, usr = escenario["tableros"], escenario["usuarios"]
    equipo_a1, clave_a1 = _equipo(db, tab["TA1"])
    equipo_a2, clave_a2 = _equipo(db, tab["TA2"])

    with cliente_http.websocket_connect(_url(tab["TA1"])) as ws_a1, \
         cliente_http.websocket_connect(_url(tab["TA2"])) as ws_a2:
        # Se conectan uno tras otro (en las pruebas ambos comparten la misma sesión de BBDD).
        ws_a1.send_json({"token": crear_token(usr["cli_a1"].id)})
        assert ws_a1.receive_json()["tipo"] == "conectado"
        ws_a2.send_json({"token": crear_token(usr["cli_a2"].id)})
        assert ws_a2.receive_json()["tipo"] == "conectado"

        # El equipo de TA1 envía datos → solo lo ve quien mira TA1.
        cliente_http.post("/ingesta", headers={"Authorization": f"Bearer {clave_a1}"})
        evento = ws_a1.receive_json()
        assert evento["tipo"] == "comunicacion" and evento["dispositivo_id"] == equipo_a1.id

        # El equipo de TA2 envía datos → lo PRIMERO que recibe TA2 es su propio evento
        # (prueba que no le llegó el de TA1).
        cliente_http.post("/ingesta", headers={"Authorization": f"Bearer {clave_a2}"})
        assert ws_a2.receive_json()["dispositivo_id"] == equipo_a2.id


def test_alarma_del_vigilante_llega_en_vivo(cliente_http, db, escenario):
    ta1, emp_a = escenario["tableros"]["TA1"], escenario["usuarios"]["emp_a"]
    ahora = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)
    equipo, _ = _equipo(db, ta1, ultima=ahora - timedelta(minutes=10))

    with cliente_http.websocket_connect(_url(ta1)) as ws:
        ws.send_json({"token": crear_token(emp_a.id)})
        ws.receive_json()  # conectado
        revisar_equipos(db, ahora, notificar=canal.publicar_desde_hilo)
        evento = ws.receive_json()
        assert evento["tipo"] == "alarma" and evento["accion"] == "creada"
        assert evento["alarma_tipo"] == "dispositivo_offline" and evento["dispositivo_id"] == equipo.id