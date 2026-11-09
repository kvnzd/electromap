"""Pruebas del cálculo de estadísticas de la prueba de carga (Etapa 20).

La prueba de carga completa se ejecuta aparte (python -m scripts.prueba_carga) porque
recrea la base de pruebas; aquí solo se verifica el resumen de tiempos y el informe.
Ejecutar desde backend/:  pytest
"""
from scripts.prueba_carga import informe, resumen_latencias


def test_resumen_de_latencias():
    r = resumen_latencias([10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 170, 180, 190, 1000])
    assert r == {"n": 20, "prom": 145, "p50": 105, "p95": 190, "max": 1000}
    assert resumen_latencias([]) == {"n": 0, "prom": None, "p50": None, "p95": None, "max": None}


def test_el_informe_marca_la_perdida_de_datos():
    r = {"parametros": {"tableros": 2, "circuitos": 1, "segundos": 3, "lectores": 1}, "duracion_s": 3.0,
         "latencia_bd_ms": 180,
         "mediciones": {"esperadas": 6, "guardadas": 5}, "ingesta": {"esperados": 6, "archivos": 6},
         "websocket": {"navegadores": 2, "avisos_esperados_c_u": 3, "avisos_min": 3, "avisos_max": 3},
         "alarmas_creadas": 0, "latencias": {"POST /ingesta": resumen_latencias([5, 7])},
         "errores": {}, "atrasos": 0, "sin_perdida": False, "sin_errores": True}
    texto = informe(r)
    assert "| Mediciones guardadas | 6 | 5 | ❌ No |" in texto
    assert "Sin pérdida de datos: ❌ No" in texto
    assert "| POST /ingesta | 2 | 6 | 6 | 7 | 7 |" in texto
    assert "**180 ms** por consulta" in texto and "misma red de Railway" in texto
