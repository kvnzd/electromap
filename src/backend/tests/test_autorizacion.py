"""Pruebas automáticas de aislamiento multi-tenant (Historias 001 y 007).

Ejecutar desde backend/:  pytest
Requieren TEST_DATABASE_URL (base de pruebas); sin ella se omiten.
"""
import logging

import pytest
from fastapi import HTTPException

from app.autorizacion import requiere_editor
from tests.conftest import auth


def codigos(respuesta) -> set[str]:
    return {t["codigo"] for t in respuesta.json()}


# ---------- Qué tableros ve cada rol ----------

def test_vsc_ve_todos_los_tableros(cliente_http, escenario):
    r = cliente_http.get("/tableros", headers=auth(escenario["usuarios"]["vsc"]))
    assert r.status_code == 200
    assert codigos(r) == {"TA1", "TA2", "TB1"}


def test_empresa_ve_solo_tableros_de_sus_clientes(cliente_http, escenario):
    r = cliente_http.get("/tableros", headers=auth(escenario["usuarios"]["emp_a"]))
    assert codigos(r) == {"TA1", "TA2"}


def test_empresa_no_ve_tableros_de_otra_empresa(cliente_http, escenario):
    r = cliente_http.get("/tableros", headers=auth(escenario["usuarios"]["emp_b"]))
    assert codigos(r) == {"TB1"}


def test_cliente_ve_solo_sus_propios_tableros(cliente_http, escenario):
    r = cliente_http.get("/tableros", headers=auth(escenario["usuarios"]["cli_a1"]))
    assert codigos(r) == {"TA1"}


# ---------- Acceso directo a un tablero ajeno ----------

def test_cliente_no_accede_a_tablero_de_otro_cliente_de_la_misma_empresa(cliente_http, escenario):
    ta2 = escenario["tableros"]["TA2"]
    r = cliente_http.get(f"/tableros/{ta2.id}", headers=auth(escenario["usuarios"]["cli_a1"]))
    assert r.status_code == 403


def test_empresa_no_accede_a_tablero_de_otra_empresa(cliente_http, escenario):
    ta1 = escenario["tableros"]["TA1"]
    r = cliente_http.get(f"/tableros/{ta1.id}", headers=auth(escenario["usuarios"]["emp_b"]))
    assert r.status_code == 403


def test_acceso_permitido_a_tablero_propio(cliente_http, escenario):
    ta1 = escenario["tableros"]["TA1"]
    r = cliente_http.get(f"/tableros/{ta1.id}", headers=auth(escenario["usuarios"]["cli_a1"]))
    assert r.status_code == 200
    assert r.json()["codigo"] == "TA1"


def test_intento_denegado_queda_registrado(cliente_http, escenario, caplog):
    ta2 = escenario["tableros"]["TA2"]
    with caplog.at_level(logging.WARNING, logger="electromap.seguridad"):
        cliente_http.get(f"/tableros/{ta2.id}", headers=auth(escenario["usuarios"]["cli_a1"]))
    assert any("ACCESO DENEGADO" in m and "t_cli_a1" in m for m in caplog.messages)


def test_tablero_inexistente_responde_404(cliente_http, escenario):
    r = cliente_http.get("/tableros/999999", headers=auth(escenario["usuarios"]["vsc"]))
    assert r.status_code == 404


def test_tablero_desactivado_no_aparece(cliente_http, escenario, db):
    escenario["tableros"]["TA1"].activo = False
    db.flush()
    r = cliente_http.get("/tableros", headers=auth(escenario["usuarios"]["vsc"]))
    assert "TA1" not in codigos(r)


def test_sin_sesion_no_se_ve_nada(cliente_http, escenario):
    assert cliente_http.get("/tableros").status_code == 401


def test_usuario_desactivado_pierde_acceso(cliente_http, escenario, db):
    usuario = escenario["usuarios"]["cli_a1"]
    headers = auth(usuario)  # token emitido ANTES de desactivarlo
    usuario.activo = False
    db.flush()
    assert cliente_http.get("/tableros", headers=headers).status_code == 401


# ---------- Quién puede editar ----------

@pytest.mark.parametrize("rol", ["vsc", "emp_a"])
def test_pueden_editar(escenario, rol):
    usuario = escenario["usuarios"][rol]
    assert requiere_editor(usuario) is usuario


@pytest.mark.parametrize("rol", ["cli_a1", "emp_a_lector"])
def test_no_pueden_editar(escenario, rol):
    with pytest.raises(HTTPException) as error:
        requiere_editor(escenario["usuarios"][rol])
    assert error.value.status_code == 403
