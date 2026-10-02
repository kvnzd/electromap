"""Pruebas automáticas de la API de administración (Historias 001 y 002).

Cubren: quién puede crear/editar/desactivar cada cosa, la asignación automática
del nivel de acceso al crear usuarios, y que desactivar corta el acceso.
Ejecutar desde backend/:  pytest
"""
import logging

from tests.conftest import auth


def _ids(respuesta) -> set[int]:
    return {x["id"] for x in respuesta.json()}


# ---------- Empresas: solo VSC administra ----------

def test_vsc_crea_empresa(cliente_http, escenario):
    r = cliente_http.post("/empresas", json={"nombre": "Nueva SpA", "rut": "76123456-7"},
                          headers=auth(escenario["usuarios"]["vsc"]))
    assert r.status_code == 201
    assert r.json()["nombre"] == "Nueva SpA" and r.json()["activo"] is True


def test_usuario_empresa_no_puede_crear_empresas(cliente_http, escenario):
    r = cliente_http.post("/empresas", json={"nombre": "Pirata"}, headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 403


def test_empresa_solo_ve_su_propia_empresa(cliente_http, escenario):
    u = escenario["usuarios"]["emp_a"]
    r = cliente_http.get("/empresas", headers=auth(u))
    assert _ids(r) == {u.empresa_id}


def test_desactivar_empresa_corta_el_acceso_de_sus_usuarios_y_clientes(cliente_http, escenario):
    usr = escenario["usuarios"]
    empresa_a = usr["emp_a"].empresa_id
    r = cliente_http.patch(f"/empresas/{empresa_a}", json={"activo": False}, headers=auth(usr["vsc"]))
    assert r.status_code == 200 and r.json()["activo"] is False
    # Usuario de la empresa y usuario de un cliente de esa empresa pierden acceso.
    assert cliente_http.get("/auth/me", headers=auth(usr["emp_a"])).status_code == 401
    assert cliente_http.get("/auth/me", headers=auth(usr["cli_a1"])).status_code == 401
    # La otra empresa no se ve afectada.
    assert cliente_http.get("/auth/me", headers=auth(usr["emp_b"])).status_code == 200


# ---------- Clientes ----------

def test_empresa_editora_crea_cliente_en_su_empresa_automaticamente(cliente_http, escenario):
    u = escenario["usuarios"]["emp_a"]
    r = cliente_http.post("/clientes", json={"nombre": "Cliente Nuevo"}, headers=auth(u))
    assert r.status_code == 201
    assert r.json()["empresa_id"] == u.empresa_id


def test_empresa_no_puede_crear_cliente_en_otra_empresa(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/clientes", json={"nombre": "X", "empresa_id": usr["emp_b"].empresa_id},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 403


def test_empresa_sin_permiso_de_edicion_no_crea_clientes(cliente_http, escenario):
    r = cliente_http.post("/clientes", json={"nombre": "X"}, headers=auth(escenario["usuarios"]["emp_a_lector"]))
    assert r.status_code == 403


def test_cliente_nunca_puede_crear_nada(cliente_http, escenario):
    h = auth(escenario["usuarios"]["cli_a1"])
    assert cliente_http.post("/clientes", json={"nombre": "X"}, headers=h).status_code == 403
    assert cliente_http.post("/sucursales", json={"cliente_id": 1, "nombre": "X"}, headers=h).status_code == 403


# ---------- Sucursales y tableros ----------

def test_empresa_no_crea_sucursal_para_cliente_de_otra_empresa(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/sucursales", json={"cliente_id": usr["cli_b1_id"], "nombre": "X"},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 403


def test_empresa_crea_tablero_en_su_sucursal(cliente_http, escenario):
    suc_a1 = escenario["tableros"]["TA1"].sucursal_id
    r = cliente_http.post("/tableros", json={"sucursal_id": suc_a1, "codigo": "TG-02", "nombre": "Tablero 2"},
                          headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 201


def test_no_crea_tablero_en_sucursal_ajena(cliente_http, escenario):
    suc_b1 = escenario["tableros"]["TB1"].sucursal_id
    r = cliente_http.post("/tableros", json={"sucursal_id": suc_b1, "codigo": "X", "nombre": "X"},
                          headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 403


def test_codigo_de_tablero_repetido_en_la_misma_sucursal_responde_409(cliente_http, escenario):
    suc_a1 = escenario["tableros"]["TA1"].sucursal_id
    r = cliente_http.post("/tableros", json={"sucursal_id": suc_a1, "codigo": "TA1", "nombre": "Duplicado"},
                          headers=auth(escenario["usuarios"]["vsc"]))
    assert r.status_code == 409


def test_desactivar_tablero_lo_saca_del_listado(cliente_http, escenario):
    ta1 = escenario["tableros"]["TA1"]
    h = auth(escenario["usuarios"]["emp_a"])
    assert cliente_http.patch(f"/tableros/{ta1.id}", json={"activo": False}, headers=h).status_code == 200
    codigos = {t["codigo"] for t in cliente_http.get("/tableros", headers=h).json()}
    assert "TA1" not in codigos


# ---------- Usuarios: asignación del nivel de acceso ----------

def test_vsc_crea_usuario_empresa_y_puede_iniciar_sesion(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/usuarios", headers=auth(usr["vsc"]), json={
        "nombre_usuario": "nuevo_emp", "password": "ClaveSegura123", "rol": "empresa",
        "empresa_id": usr["emp_a"].empresa_id, "puede_editar": True,
    })
    assert r.status_code == 201
    datos = r.json()
    assert datos["rol"] == "empresa" and datos["empresa_id"] == usr["emp_a"].empresa_id
    assert "password" not in datos and "password_hash" not in datos

    login = cliente_http.post("/auth/login", data={"username": "nuevo_emp", "password": "ClaveSegura123"})
    assert login.status_code == 200


def test_empresa_crea_usuario_para_su_cliente(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/usuarios", headers=auth(usr["emp_a"]), json={
        "nombre_usuario": "nuevo_cli", "password": "ClaveSegura123", "rol": "cliente",
        "cliente_id": usr["cli_a1"].cliente_id,
    })
    assert r.status_code == 201
    assert r.json()["puede_editar"] is False


def test_empresa_crea_usuario_empresa_queda_en_su_propia_empresa(cliente_http, escenario):
    u = escenario["usuarios"]["emp_a"]
    r = cliente_http.post("/usuarios", headers=auth(u), json={
        "nombre_usuario": "colega", "password": "ClaveSegura123", "rol": "empresa",
    })
    assert r.status_code == 201
    assert r.json()["empresa_id"] == u.empresa_id


def test_empresa_no_crea_usuario_para_cliente_de_otra_empresa(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/usuarios", headers=auth(usr["emp_a"]), json={
        "nombre_usuario": "intruso", "password": "ClaveSegura123", "rol": "cliente",
        "cliente_id": usr["cli_b1_id"],
    })
    assert r.status_code == 403


def test_empresa_no_puede_crear_usuarios_vsc(cliente_http, escenario):
    r = cliente_http.post("/usuarios", headers=auth(escenario["usuarios"]["emp_a"]), json={
        "nombre_usuario": "falso_admin", "password": "ClaveSegura123", "rol": "vsc",
    })
    assert r.status_code == 403


def test_usuario_cliente_con_permiso_de_edicion_se_rechaza(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/usuarios", headers=auth(usr["vsc"]), json={
        "nombre_usuario": "cli_editor", "password": "ClaveSegura123", "rol": "cliente",
        "cliente_id": usr["cli_a1"].cliente_id, "puede_editar": True,
    })
    assert r.status_code == 400


def test_nombre_de_usuario_repetido_responde_409(cliente_http, escenario):
    usr = escenario["usuarios"]
    r = cliente_http.post("/usuarios", headers=auth(usr["vsc"]), json={
        "nombre_usuario": usr["emp_a"].nombre_usuario, "password": "ClaveSegura123", "rol": "vsc",
    })
    assert r.status_code == 409


def test_password_corta_se_rechaza(cliente_http, escenario):
    r = cliente_http.post("/usuarios", headers=auth(escenario["usuarios"]["vsc"]), json={
        "nombre_usuario": "corta", "password": "123", "rol": "vsc",
    })
    assert r.status_code == 422


def test_desactivar_usuario_corta_su_acceso(cliente_http, escenario):
    usr = escenario["usuarios"]
    objetivo = usr["cli_a1"]
    r = cliente_http.patch(f"/usuarios/{objetivo.id}", json={"activo": False}, headers=auth(usr["emp_a"]))
    assert r.status_code == 200
    assert cliente_http.get("/auth/me", headers=auth(objetivo)).status_code == 401


def test_nadie_puede_desactivarse_a_si_mismo(cliente_http, escenario):
    u = escenario["usuarios"]["vsc"]
    r = cliente_http.patch(f"/usuarios/{u.id}", json={"activo": False}, headers=auth(u))
    assert r.status_code == 400


def test_cliente_solo_se_ve_a_si_mismo(cliente_http, escenario):
    u = escenario["usuarios"]["cli_a1"]
    assert _ids(cliente_http.get("/usuarios", headers=auth(u))) == {u.id}


def test_creacion_de_usuario_queda_en_auditoria(cliente_http, escenario, caplog):
    usr = escenario["usuarios"]
    with caplog.at_level(logging.INFO, logger="electromap.auditoria"):
        cliente_http.post("/usuarios", headers=auth(usr["vsc"]), json={
            "nombre_usuario": "auditado", "password": "ClaveSegura123", "rol": "vsc",
        })
    assert any("CREA usuario" in m and "auditado" in m for m in caplog.messages)
    # La contraseña nunca aparece en los registros.
    assert not any("ClaveSegura123" in m for m in caplog.messages)
