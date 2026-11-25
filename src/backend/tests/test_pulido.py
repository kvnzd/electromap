"""Pruebas automáticas del pulido y seguridad (Etapa 23).

Cubren: los secretos no aparecen al mostrar la configuración (por ejemplo en un error),
los registros de las pruebas no van a la carpeta logs/ real, /health no entrega la versión
de PostgreSQL, /health/schema es solo para VSC y el mensaje del canal es legible.
Ejecutar desde backend/:  pytest
"""
import logging
from pathlib import Path

from app.config import settings
from tests.conftest import auth

CARPETA_LOGS_REAL = Path(__file__).resolve().parents[1] / "logs"


def test_la_configuracion_no_muestra_secretos():
    texto = repr(settings) + str(settings)
    assert settings.database_url.get_secret_value() not in texto
    assert settings.jwt_secret.get_secret_value() not in texto
    assert "**********" in texto


def test_los_registros_de_las_pruebas_no_van_a_logs_real():
    assert settings.logs_carpeta.resolve() != CARPETA_LOGS_REAL.resolve()
    archivos = [Path(h.baseFilename) for h in logging.getLogger("electromap.auditoria").handlers
                if isinstance(h, logging.FileHandler)]
    assert archivos and all(a.parent == settings.logs_carpeta for a in archivos)


def test_health_no_entrega_la_version_de_postgresql(cliente_http):
    r = cliente_http.get("/health")
    assert r.status_code == 200
    assert r.json()["base_de_datos"] == "conectada"
    assert "PostgreSQL" not in r.text


def test_health_schema_es_solo_para_vsc(cliente_http, escenario):
    assert cliente_http.get("/health/schema").status_code == 401
    r = cliente_http.get("/health/schema", headers=auth(escenario["usuarios"]["emp_a"]))
    assert r.status_code == 403


def test_mensaje_del_canal_es_legible(cliente_http, escenario):
    r = cliente_http.post("/circuitos", headers=auth(escenario["usuarios"]["vsc"]), json={
        "tablero_id": escenario["tableros"]["TA1"].id, "codigo": "C9", "nombre": "Prueba", "canal_acurev": "1"})
    assert r.status_code == 400
    assert "canal del AcuRev" in r.json()["detail"] and "canal_acurev" not in r.json()["detail"]
