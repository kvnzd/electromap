"""Pruebas automáticas del listado y cierre manual de alarmas (Etapa 15 — Historia 005).

Cubren: filtro abiertas/resueltas/todas, orden (la más reciente primero), quién la cerró
(sistema o persona), permisos (cliente solo lee, empresa ajena 403), alarma ya resuelta (409)
y el aviso por el WebSocket al cerrarla.
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone

from app.models import Alarma, Dispositivo
from app.security import crear_token
from tests.conftest import auth

AHORA = datetime(2026, 11, 9, 15, 0, tzinfo=timezone.utc)


def _alarmas(db, tablero):
    equipo = Dispositivo(tablero_id=tablero.id, numero_serie=f"EQ-{tablero.codigo}")
    db.add(equipo); db.flush()
    abierta = Alarma(dispositivo_id=equipo.id, tipo="dispositivo_offline", severidad="critica",
                     mensaje="abierta", generado_en=AHORA)
    sistema = Alarma(dispositivo_id=equipo.id, tipo="umbral_corriente", severidad="moderada", mensaje="cerró el sistema",
                     generado_en=AHORA - timedelta(hours=1), resuelto=True, resuelto_en=AHORA)
    db.add_all([abierta, sistema]); db.flush()
    return equipo, abierta, sistema


def test_listar_por_estado_y_orden(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    _alarmas(db, ta1)
    _alarmas(db, escenario["tableros"]["TA2"])   # de otro tablero: no aparece
    h = auth(escenario["usuarios"]["cli_a1"])     # un cliente puede ver las alarmas de su tablero
    abiertas = cliente_http.get("/alarmas", params={"tablero_id": ta1.id}, headers=h).json()
    assert [a["mensaje"] for a in abiertas] == ["abierta"]
    todas = cliente_http.get("/alarmas", params={"tablero_id": ta1.id, "estado": "todas"}, headers=h).json()
    assert [a["mensaje"] for a in todas] == ["abierta", "cerró el sistema"]
    [resuelta] = cliente_http.get("/alarmas", params={"tablero_id": ta1.id, "estado": "resueltas"}, headers=h).json()
    assert resuelta["resuelto"] is True and resuelta["resuelto_por"] is None and resuelta["resuelto_por_nombre"] is None


def test_alarmas_de_tablero_ajeno_responde_403(cliente_http, escenario):
    r = cliente_http.get("/alarmas", params={"tablero_id": escenario["tableros"]["TB1"].id},
                         headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 403


def test_editor_resuelve_a_mano_y_queda_registrado(cliente_http, db, escenario):
    ta1 = escenario["tableros"]["TA1"]
    _, abierta, sistema = _alarmas(db, ta1)
    editor = escenario["usuarios"]["emp_a"]
    with cliente_http.websocket_connect(f"/ws/tableros/{ta1.id}") as ws:
        ws.send_json({"token": crear_token(editor.id)})
        ws.receive_json()  # conectado
        r = cliente_http.patch(f"/alarmas/{abierta.id}/resolver", headers=auth(editor))
        evento = ws.receive_json()
    assert r.status_code == 200
    assert r.json()["resuelto"] is True and r.json()["resuelto_por"] == editor.id
    assert r.json()["resuelto_por_nombre"] == "t_emp_a"
    assert evento["tipo"] == "alarma" and evento["accion"] == "resuelta" and evento["alarma_id"] == abierta.id
    # Ya resuelta (a mano o por el sistema) → 409.
    assert cliente_http.patch(f"/alarmas/{abierta.id}/resolver", headers=auth(editor)).status_code == 409
    assert cliente_http.patch(f"/alarmas/{sistema.id}/resolver", headers=auth(editor)).status_code == 409


def test_cliente_y_empresa_ajena_no_pueden_resolver(cliente_http, db, escenario):
    _, abierta, _ = _alarmas(db, escenario["tableros"]["TA1"])
    u = escenario["usuarios"]
    assert cliente_http.patch(f"/alarmas/{abierta.id}/resolver", headers=auth(u["cli_a1"])).status_code == 403
    assert cliente_http.patch(f"/alarmas/{abierta.id}/resolver", headers=auth(u["emp_b"])).status_code == 403
    assert cliente_http.patch("/alarmas/999999/resolver", headers=auth(u["vsc"])).status_code == 404
    db.refresh(abierta)
    assert abierta.resuelto is False
