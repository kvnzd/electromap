"""Pruebas del lector del CSV del AcuRev (Etapa 12).

Usan el PRIMER ENVÍO REAL del equipo (25-11-2026, 22:41), guardado en
tests/datos/acurev_envio_real_2026-11-25.txt (solo el cuerpo: sin cabeceras,
sin clave y sin IP). Valores esperados del canal 001 en ese envío:
Va_V = 229,795 V · I001_A = 1,228 A · P001_kW = 0,222 kW · EP001_IMP_kWh = 0,5 kWh.

Las pruebas de la parte 1 no usan la base de datos; las de la parte 2 sí
(se omiten si TEST_DATABASE_URL no está configurada).
Ejecutar desde src/backend/:  pytest tests/test_lector_csv.py
"""
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.config import settings
from app.lector_csv import (
    FormatoInvalido,
    canales,
    extraer_csv,
    leer_filas,
    leer_hora,
    mediciones_del_envio,
)
from app.models import Circuito, Dispositivo, Medicion
from app.security import generar_clave_ingesta, hashear_clave_ingesta

ENVIO_REAL = (Path(__file__).parent / "datos" / "acurev_envio_real_2026-11-25.txt").read_bytes()
TIPO_REAL = "multipart/form-data; boundary=------------------------bd89d919cbfa4f03"
MINUTO_REAL = datetime(2026, 11, 26, 1, 40, tzinfo=timezone.utc)  # 22:40 -03:00


def _filas_reales():
    [(nombre, texto)] = extraer_csv(ENVIO_REAL, TIPO_REAL)
    return nombre, leer_filas(texto)


def _circuito(id_, canal):
    return SimpleNamespace(id=id_, canal_acurev=canal)


# ---------- 1. Lectura del formato (sin base de datos) ----------

def test_extrae_el_archivo_csv_del_multipart_real():
    nombre, filas = _filas_reales()
    assert nombre == "EHM23080411-logger1-2026-11-25T22-41-00-0300-1min.csv"
    assert len(filas) == 1                      # 1 fila por envío (1 minuto)
    assert len(filas[0]) == 111                 # 111 columnas
    assert filas[0]["Time"] == "2026-11-25T22:40:00-0300"


def test_hora_iso_con_offset_sin_y_con_dos_puntos():
    assert leer_hora("2026-11-25T22:40:00-0300") == MINUTO_REAL
    assert leer_hora("2026-11-25T22:40:00-03:00") == MINUTO_REAL
    with pytest.raises(FormatoInvalido):
        leer_hora("25/11/2026 22:40")


def test_canal_001_monofasico_con_unidades_de_la_base():
    _, filas = _filas_reales()
    [m], avisos = mediciones_del_envio(filas, equipo_id=1, circuitos=[_circuito(7, "001")])
    assert avisos == []
    assert m["circuito_id"] == 7 and m["dispositivo_id"] == 1
    assert m["medido_en"] == MINUTO_REAL
    assert m["voltaje_a"] == 229.795
    assert m["corriente_a"] == 1.228            # I001_A, NO Ia_A (1,092) ni Iavg_A
    assert m["potencia_activa"] == 222.0        # 0,222 kW → 222 W (la base guarda W)
    assert m["energia_kwh"] == 0.5
    assert "voltaje_b" not in m                 # B y C no se inventan (Vb_V ≈ 130 V es inducido)


def test_canal_escrito_como_1_es_el_mismo_que_001():
    assert canales("1") == canales("001") == ["001"]
    assert canales("2, 3, 4") == ["002", "003", "004"]
    assert canales("C1") == [] and canales("19") == [] and canales("1,2,3,4") == []


def test_trifasico_suma_potencia_y_energia_de_sus_tres_canales():
    fila = {"Time": "2026-11-25T22:40:00-0300", "Va_V": "220", "Vb_V": "221", "Vc_V": "222",
            "I002_A": "10", "P002_kW": "2.0", "EP002_IMP_kWh": "1.5",
            "I003_A": "11", "P003_kW": "2.1", "EP003_IMP_kWh": "1.0",
            "I004_A": "12", "P004_kW": "2.2", "EP004_IMP_kWh": "0.5"}
    [m], _ = mediciones_del_envio([fila], 1, [_circuito(9, "002,003,004")])
    assert (m["corriente_a"], m["corriente_b"], m["corriente_c"]) == (10, 11, 12)
    assert (m["voltaje_a"], m["voltaje_c"]) == (220, 222)
    assert m["potencia_activa"] == 6300.0 and m["energia_kwh"] == 3.0


def test_canal_invalido_o_sin_columna_se_avisa_y_no_se_inventa():
    _, filas = _filas_reales()
    mediciones, avisos = mediciones_del_envio(filas, 1, [_circuito(7, "C1")])
    assert mediciones == [] and any("no válido" in a for a in avisos)


def test_tambien_acepta_el_csv_sin_multipart():
    texto = "Time,Va_V,I001_A,P001_kW,EP001_IMP_kWh\r\n2026-11-25T22:40:00-0300,229.8,1.2,0.22,0.5\r\n\r\n"
    [(nombre, contenido)] = extraer_csv(texto.encode(), "text/csv")
    [m], _ = mediciones_del_envio(leer_filas(contenido), 1, [_circuito(7, "001")])
    assert nombre is None and m["potencia_activa"] == 220.0


def test_csv_sin_columna_time_es_formato_invalido():
    with pytest.raises(FormatoInvalido):
        leer_filas("fecha,canal,corriente\n2026-11-03 19:00:00,1,12.5\n")


# ---------- 2. Envío real completo por /ingesta (con base de datos) ----------

@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ingesta_carpeta", tmp_path)
    return tmp_path


@pytest.fixture
def equipo_con_circuito(db, escenario):
    """AcuRev en TA1 con el circuito 'C1 PRUEBA' en el canal 001 (como en la casa de Kevin)."""
    clave = generar_clave_ingesta()
    tablero = escenario["tableros"]["TA1"]
    d = Dispositivo(tablero_id=tablero.id, numero_serie="EHM-TEST", token_ingesta=hashear_clave_ingesta(clave))
    db.add(d); db.flush()
    c = Circuito(tablero_id=tablero.id, dispositivo_id=d.id, codigo="C1", nombre="C1 PRUEBA", canal_acurev="001")
    db.add(c); db.flush()
    return d, c, clave


def _enviar(cliente_http, clave):
    return cliente_http.post("/ingesta", content=ENVIO_REAL, auth=("acurev", clave),
                             headers={"Content-Type": TIPO_REAL})


def test_envio_real_queda_como_medicion_del_circuito(cliente_http, db, carpeta, equipo_con_circuito):
    dispositivo, circuito, clave = equipo_con_circuito
    r = _enviar(cliente_http, clave)
    assert r.status_code == 200
    assert r.json()["filas_csv"] == 1 and r.json()["mediciones_nuevas"] == 1 and r.json()["avisos"] == []

    m = db.scalar(select(Medicion).where(Medicion.circuito_id == circuito.id))
    assert m.dispositivo_id == dispositivo.id and m.medido_en == MINUTO_REAL
    assert float(m.voltaje_a) == 229.8 and float(m.corriente_a) == 1.23   # NUMERIC(…,2) redondea
    assert float(m.potencia_activa) == 222.0 and float(m.energia_kwh) == 0.5
    assert list((carpeta / f"dispositivo_{dispositivo.id}").glob("*_cuerpo.txt"))  # el crudo se sigue guardando


def test_reenvio_del_mismo_minuto_no_duplica(cliente_http, db, carpeta, equipo_con_circuito):
    _, circuito, clave = equipo_con_circuito
    assert _enviar(cliente_http, clave).json()["mediciones_nuevas"] == 1
    assert _enviar(cliente_http, clave).json()["mediciones_nuevas"] == 0   # p. ej. reenvío del buffer
    total = db.scalars(select(Medicion).where(Medicion.circuito_id == circuito.id)).all()
    assert len(total) == 1


def test_equipo_sin_canal_configurado_guarda_el_crudo_y_avisa(cliente_http, db, carpeta, equipo_con_circuito):
    _, circuito, clave = equipo_con_circuito
    circuito.canal_acurev = None; db.flush()
    r = _enviar(cliente_http, clave)
    assert r.status_code == 200 and r.json()["mediciones_nuevas"] == 0
    assert any("canal_acurev" in a for a in r.json()["avisos"])



def _crear_circuito(cliente_http, escenario, dispositivo, codigo, canal):
    from tests.conftest import auth
    datos = {"tablero_id": escenario["tableros"]["TA1"].id, "dispositivo_id": dispositivo.id,
             "codigo": codigo, "nombre": "X", "canal_acurev": canal}
    return cliente_http.post("/circuitos", json=datos, headers=auth(escenario["usuarios"]["emp_a"]))


def test_canal_con_nombre_c1_se_rechaza(cliente_http, escenario, equipo_con_circuito):
    r = _crear_circuito(cliente_http, escenario, equipo_con_circuito[0], "C7", "C1")
    assert r.status_code == 400 and "número del canal" in r.json()["detail"]


def test_canal_1_es_el_mismo_001_y_no_se_duplica(cliente_http, escenario, equipo_con_circuito):
    r = _crear_circuito(cliente_http, escenario, equipo_con_circuito[0], "C8", "1")
    assert r.status_code == 409                 # C1 PRUEBA ya usa el canal 001


def test_canal_trifasico_se_guarda_con_tres_digitos(cliente_http, escenario, equipo_con_circuito):
    r = _crear_circuito(cliente_http, escenario, equipo_con_circuito[0], "C9", "2, 3, 4")
    assert r.status_code == 201 and r.json()["canal_acurev"] == "002,003,004"
