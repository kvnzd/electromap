"""Pruebas automáticas de dispositivos y circuitos (Etapa 10).

Cubren: la clave de ingesta se entrega una sola vez y en la BBDD queda solo su hash,
regenerar invalida la anterior, aislamiento por empresa/cliente, y las reglas
de conexión de los circuitos (equipo, canal, calibre, duplicados).
Ejecutar desde backend/:  pytest
"""
from decimal import Decimal

from app.models import CalibreCable, Dispositivo
from app.security import hashear_clave_ingesta
from tests.conftest import auth


# ---------- Ayudas ----------

def _dispositivo(db, tablero, serie="SN-1") -> Dispositivo:
    """Crea un equipo directo en la BBDD de pruebas (sin pasar por la API)."""
    d = Dispositivo(tablero_id=tablero.id, numero_serie=serie,
                    token_ingesta=hashear_clave_ingesta(f"clave-{serie}"))
    db.add(d); db.flush()
    return d


def _ids(respuesta) -> set[int]:
    return {x["id"] for x in respuesta.json()}


# ---------- Dispositivos: clave de ingesta ----------

def test_crear_dispositivo_entrega_clave_una_vez_y_guarda_solo_el_hash(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    r = cliente_http.post("/dispositivos", json={"tablero_id": tab["TA1"].id, "numero_serie": "AR-001"},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 201
    clave = r.json()["clave_ingesta"]
    assert clave.startswith("em_")

    # En la BBDD queda el hash SHA-256 (64 caracteres), nunca la clave en texto plano.
    guardado = db.get(Dispositivo, r.json()["id"])
    assert guardado.token_ingesta == hashear_clave_ingesta(clave)
    assert guardado.token_ingesta != clave and len(guardado.token_ingesta) == 64

    # Al consultarlo después, la clave ya no se muestra (ni el hash).
    r2 = cliente_http.get(f"/dispositivos/{guardado.id}", headers=auth(usr["emp_a"]))
    assert r2.status_code == 200
    assert "clave_ingesta" not in r2.json() and "token_ingesta" not in r2.json()


def test_regenerar_clave_invalida_la_anterior(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    creado = cliente_http.post("/dispositivos", json={"tablero_id": tab["TA1"].id},
                               headers=auth(usr["emp_a"])).json()
    r = cliente_http.post(f"/dispositivos/{creado['id']}/regenerar-clave", headers=auth(usr["emp_a"]))
    assert r.status_code == 200
    nueva = r.json()["clave_ingesta"]
    assert nueva != creado["clave_ingesta"]

    guardado = db.get(Dispositivo, creado["id"])
    assert guardado.token_ingesta == hashear_clave_ingesta(nueva)
    assert guardado.token_ingesta != hashear_clave_ingesta(creado["clave_ingesta"])


# ---------- Dispositivos: permisos y alcance ----------

def test_cliente_no_puede_crear_dispositivos(cliente_http, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    r = cliente_http.post("/dispositivos", json={"tablero_id": tab["TA1"].id}, headers=auth(usr["cli_a1"]))
    assert r.status_code == 403


def test_empresa_no_puede_crear_dispositivo_en_tablero_de_otra_empresa(cliente_http, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    r = cliente_http.post("/dispositivos", json={"tablero_id": tab["TB1"].id}, headers=auth(usr["emp_a"]))
    assert r.status_code == 403


def test_cliente_solo_ve_los_dispositivos_de_sus_tableros(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    propio = _dispositivo(db, tab["TA1"], "P-1")
    ajeno = _dispositivo(db, tab["TA2"], "A-1")
    r = cliente_http.get("/dispositivos", headers=auth(usr["cli_a1"]))
    assert _ids(r) == {propio.id}
    assert cliente_http.get(f"/dispositivos/{ajeno.id}", headers=auth(usr["cli_a1"])).status_code == 403


# ---------- Circuitos: reglas de conexión ----------

def test_crear_circuito_conectado_a_su_equipo(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    equipo = _dispositivo(db, tab["TA1"])
    r = cliente_http.post("/circuitos", json={"tablero_id": tab["TA1"].id, "dispositivo_id": equipo.id,
                                              "codigo": "C1", "nombre": "Alumbrado", "canal_acurev": "1"},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 201
    assert r.json()["dispositivo_id"] == equipo.id and r.json()["canal_acurev"] == "1"


def test_circuito_no_acepta_equipo_de_otro_tablero(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    equipo_ta2 = _dispositivo(db, tab["TA2"])
    r = cliente_http.post("/circuitos", json={"tablero_id": tab["TA1"].id, "dispositivo_id": equipo_ta2.id,
                                              "codigo": "C1", "nombre": "X"},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 400


def test_circuito_no_acepta_canal_sin_equipo(cliente_http, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    r = cliente_http.post("/circuitos", json={"tablero_id": tab["TA1"].id, "codigo": "C1",
                                              "nombre": "X", "canal_acurev": "1"},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 400


def test_circuito_valida_que_el_calibre_exista(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    base = {"tablero_id": tab["TA1"].id, "nombre": "Enchufes"}
    # Calibre que no está en la tabla → 400
    r = cliente_http.post("/circuitos", json={**base, "codigo": "C1", "calibre_cable_mm2": 2.5},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 400
    # Se carga el calibre (solo en la base de PRUEBAS) → ahora sí se acepta
    db.add(CalibreCable(calibre_mm2=Decimal("2.5"), corriente_maxima=Decimal("20"))); db.flush()
    r = cliente_http.post("/circuitos", json={**base, "codigo": "C2", "calibre_cable_mm2": 2.5},
                          headers=auth(usr["emp_a"]))
    assert r.status_code == 201 and r.json()["calibre_cable_mm2"] == 2.5


def test_codigo_y_canal_repetidos_responden_409(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    equipo = _dispositivo(db, tab["TA1"])
    h = auth(usr["emp_a"])
    base = {"tablero_id": tab["TA1"].id, "dispositivo_id": equipo.id, "nombre": "X"}
    assert cliente_http.post("/circuitos", json={**base, "codigo": "C1", "canal_acurev": "1"}, headers=h).status_code == 201
    # Mismo código en el mismo tablero
    assert cliente_http.post("/circuitos", json={**base, "codigo": "C1", "canal_acurev": "2"}, headers=h).status_code == 409
    # Mismo canal en el mismo equipo
    assert cliente_http.post("/circuitos", json={**base, "codigo": "C2", "canal_acurev": "1"}, headers=h).status_code == 409


def test_cliente_no_ve_circuitos_de_otro_cliente(cliente_http, db, escenario):
    usr, tab = escenario["usuarios"], escenario["tableros"]
    creado = cliente_http.post("/circuitos", json={"tablero_id": tab["TA2"].id, "codigo": "C1", "nombre": "X"},
                               headers=auth(usr["emp_a"])).json()
    assert cliente_http.get("/circuitos", headers=auth(usr["cli_a1"])).json() == []
    assert cliente_http.get(f"/circuitos/{creado['id']}", headers=auth(usr["cli_a1"])).status_code == 403