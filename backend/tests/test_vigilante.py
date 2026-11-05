"""Pruebas automáticas del vigilante de equipos desconectados (Etapa 13).

Cubren: alarma al superar el límite sin datos, sin duplicados, equipos recientes,
nunca conectados o inactivos no generan alarma, y resolución automática al volver.
Se usa una hora fija ("AHORA") para que las pruebas no dependan del reloj.
Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.config import settings
from app.models import Alarma, Dispositivo
from app.vigilante import TIPO_OFFLINE, revisar_equipos

AHORA = datetime(2026, 11, 4, 12, 0, tzinfo=timezone.utc)


def _equipo(db, escenario, minutos_sin_datos, activo=True, serie="AR-V"):
    """Equipo cuya última comunicación fue hace `minutos_sin_datos` (None = nunca)."""
    ultima = None if minutos_sin_datos is None else AHORA - timedelta(minutes=minutos_sin_datos)
    d = Dispositivo(tablero_id=escenario["tableros"]["TA1"].id, numero_serie=serie,
                    ultima_comunicacion=ultima, activo=activo)
    db.add(d); db.flush()
    return d


def _alarmas(db, equipo):
    return db.scalars(select(Alarma).where(Alarma.dispositivo_id == equipo.id,
                                           Alarma.tipo == TIPO_OFFLINE)).all()


def test_equipo_sin_datos_genera_alarma_critica(db, escenario):
    equipo = _equipo(db, escenario, minutos_sin_datos=10)
    assert revisar_equipos(db, AHORA) == {"creadas": 1, "resueltas": 0}
    [alarma] = _alarmas(db, equipo)
    assert alarma.severidad == "critica" and alarma.resuelto is False
    assert alarma.circuito_id is None                      # es del equipo, no de un circuito
    assert alarma.valor_medido == 10 and alarma.valor_umbral == settings.offline_minutos


def test_no_duplica_la_alarma_si_sigue_desconectado(db, escenario):
    equipo = _equipo(db, escenario, minutos_sin_datos=10)
    revisar_equipos(db, AHORA)
    assert revisar_equipos(db, AHORA + timedelta(minutes=1)) == {"creadas": 0, "resueltas": 0}
    assert len(_alarmas(db, equipo)) == 1


def test_equipo_que_envio_hace_poco_no_genera_alarma(db, escenario):
    equipo = _equipo(db, escenario, minutos_sin_datos=2)
    revisar_equipos(db, AHORA)
    assert _alarmas(db, equipo) == []


def test_equipo_que_nunca_se_conecto_no_cuenta_como_desconectado(db, escenario):
    equipo = _equipo(db, escenario, minutos_sin_datos=None)
    revisar_equipos(db, AHORA)
    assert _alarmas(db, equipo) == []


def test_equipo_inactivo_no_genera_alarma(db, escenario):
    equipo = _equipo(db, escenario, minutos_sin_datos=60, activo=False)
    revisar_equipos(db, AHORA)
    assert _alarmas(db, equipo) == []


def test_al_volver_se_resuelve_sola_y_si_cae_otra_vez_se_crea_una_nueva(db, escenario):
    equipo = _equipo(db, escenario, minutos_sin_datos=10)
    revisar_equipos(db, AHORA)

    # El equipo vuelve a enviar datos (como haría /ingesta).
    equipo.ultima_comunicacion = AHORA + timedelta(minutes=1)
    db.flush()
    assert revisar_equipos(db, AHORA + timedelta(minutes=2)) == {"creadas": 0, "resueltas": 1}
    [alarma] = _alarmas(db, equipo)
    assert alarma.resuelto is True and alarma.resuelto_en is not None
    assert alarma.resuelto_por is None                     # la resolvió el sistema, no una persona

    # Se vuelve a caer: queda la anterior resuelta y una nueva abierta.
    revisar_equipos(db, AHORA + timedelta(minutes=20))
    alarmas = _alarmas(db, equipo)
    assert len(alarmas) == 2
    assert sum(1 for a in alarmas if not a.resuelto) == 1