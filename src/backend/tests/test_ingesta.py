"""Pruebas automáticas del receptor de ingesta del AcuRev (Etapa 11).

Cubren: autenticación por clave (Basic y Bearer), rechazo y registro de claves
inválidas o equipos inactivos, guardado del envío tal cual llega (sin guardar
la clave), envío vacío como prueba de conexión y límite de tamaño.
Los archivos se escriben en una carpeta temporal (tmp_path), nunca en la real.
Ejecutar desde backend/:  pytest
"""
import logging

import pytest

from app.config import settings
from app.models import Dispositivo
from app.security import generar_clave_ingesta, hashear_clave_ingesta

CSV_EJEMPLO = b"fecha,canal,corriente\n2026-11-03 19:00:00,1,12.5\n"


@pytest.fixture
def carpeta(tmp_path, monkeypatch):
    """Durante cada prueba, los envíos se guardan en una carpeta temporal."""
    monkeypatch.setattr(settings, "ingesta_carpeta", tmp_path)
    return tmp_path


@pytest.fixture
def equipo(db, escenario):
    """Un AcuRev registrado en el tablero TA1, con su clave en texto plano para las pruebas."""
    clave = generar_clave_ingesta()
    d = Dispositivo(tablero_id=escenario["tableros"]["TA1"].id, numero_serie="AR-TEST",
                    token_ingesta=hashear_clave_ingesta(clave))
    db.add(d); db.flush()
    return d, clave


# ---------- Rechazos ----------

def test_sin_clave_responde_401_con_desafio_basic(cliente_http, carpeta):
    r = cliente_http.post("/ingesta", content=CSV_EJEMPLO)
    assert r.status_code == 401
    assert r.headers["www-authenticate"].startswith("Basic")
    assert list(carpeta.iterdir()) == []  # no se guardó nada


def test_clave_invalida_se_rechaza_y_queda_registrada(cliente_http, carpeta, equipo, caplog):
    with caplog.at_level(logging.WARNING, logger="electromap.seguridad"):
        r = cliente_http.post("/ingesta", content=CSV_EJEMPLO,
                              headers={"Authorization": "Bearer em_inventada"})
    assert r.status_code == 401
    assert "INGESTA RECHAZADA" in caplog.text
    assert list(carpeta.iterdir()) == []


def test_equipo_inactivo_no_puede_enviar(cliente_http, db, carpeta, equipo):
    dispositivo, clave = equipo
    dispositivo.activo = False; db.flush()
    r = cliente_http.post("/ingesta", content=CSV_EJEMPLO, headers={"Authorization": f"Bearer {clave}"})
    assert r.status_code == 401


def test_envio_demasiado_grande_responde_413(cliente_http, carpeta, equipo, monkeypatch):
    _, clave = equipo
    monkeypatch.setattr(settings, "ingesta_max_bytes", 10)
    r = cliente_http.post("/ingesta", content=CSV_EJEMPLO, headers={"Authorization": f"Bearer {clave}"})
    assert r.status_code == 413
    assert list(carpeta.iterdir()) == []


# ---------- Envíos aceptados ----------

def test_bearer_valido_guarda_el_envio_tal_cual_y_sin_la_clave(cliente_http, db, carpeta, equipo):
    dispositivo, clave = equipo
    r = cliente_http.post("/ingesta", content=CSV_EJEMPLO,
                          headers={"Authorization": f"Bearer {clave}", "Content-Type": "text/csv"})
    assert r.status_code == 200
    assert r.json()["dispositivo_id"] == dispositivo.id and r.json()["bytes"] == len(CSV_EJEMPLO)

    carpeta_equipo = carpeta / f"dispositivo_{dispositivo.id}"
    [cuerpo] = list(carpeta_equipo.glob("*_cuerpo.txt"))
    [cabeceras] = list(carpeta_equipo.glob("*_cabeceras.txt"))
    assert cuerpo.read_bytes() == CSV_EJEMPLO          # idéntico byte a byte
    texto = cabeceras.read_text(encoding="utf-8")
    assert "text/csv" in texto                          # sirve para conocer el formato
    assert clave not in texto and "authorization" not in texto.lower()  # la clave NUNCA se guarda

    db.refresh(dispositivo)
    assert dispositivo.ultima_comunicacion is not None


def test_basic_valido_tambien_se_acepta(cliente_http, carpeta, equipo):
    dispositivo, clave = equipo
    r = cliente_http.post("/ingesta", content=CSV_EJEMPLO, auth=("acurev", clave))
    assert r.status_code == 200 and r.json()["dispositivo_id"] == dispositivo.id


def test_envio_vacio_es_prueba_de_conexion(cliente_http, db, carpeta, equipo):
    dispositivo, clave = equipo
    r = cliente_http.post("/ingesta", headers={"Authorization": f"Bearer {clave}"})
    assert r.status_code == 200 and r.json()["archivo"] is None
    assert list(carpeta.iterdir()) == []                # no crea archivos
    db.refresh(dispositivo)
    assert dispositivo.ultima_comunicacion is not None  # pero sí marca que el equipo está vivo