"""Temperatura ESTIMADA del conductor (Etapa 19a): un cálculo, no una medición.

    T ≈ T_ambiente + (T_máx_aislación − T_ambiente) · (I / I_admisible)²

- I: corriente del circuito (la fase más cargada).
- I_admisible: ampacidad del calibre del cable (tabla calibres_cable: NCh Elec 4/2003,
  Tabla 8.7, grupo 1 — cobre en ducto, 3 conductores activos, ambiente 30 °C).
- T_ambiente y T_máx_aislación: configuración (por defecto 30 °C y 70 °C, aislación PVC).
Aproximación de régimen permanente: no considera el tiempo que tarda el cable en calentarse
ni factores de corrección (agrupamiento, ambiente distinto de 30 °C).
"""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CalibreCable, Circuito

_FASES = ("corriente_a", "corriente_b", "corriente_c")


def corriente_mayor(fila) -> float | None:
    """La corriente de la fase más cargada (fila: diccionario u objeto Medicion)."""
    leer = fila.get if isinstance(fila, dict) else (lambda c: getattr(fila, c))
    valores = [float(leer(f)) for f in _FASES if leer(f) is not None]
    return max(valores) if valores else None


def estimar_temperatura(corriente, ampacidad, t_ambiente: float | None = None, t_max: float | None = None) -> float | None:
    """°C estimados del conductor, o None si falta la corriente o la ampacidad del cable."""
    if corriente is None or not ampacidad:
        return None
    ta = settings.temperatura_ambiente if t_ambiente is None else t_ambiente
    tm = settings.temperatura_max_aislacion if t_max is None else t_max
    return round(ta + (tm - ta) * (float(corriente) / float(ampacidad)) ** 2, 1)


def ampacidades(db: Session, circuito_ids) -> dict[int, float | None]:
    """circuito_id → ampacidad (A) de su cable, o None si el circuito no tiene calibre asignado."""
    if not circuito_ids:
        return {}
    filas = db.execute(
        select(Circuito.id, CalibreCable.corriente_maxima)
        .outerjoin(CalibreCable, Circuito.calibre_cable_mm2 == CalibreCable.calibre_mm2)
        .where(Circuito.id.in_(list(circuito_ids)))
    ).all()
    return {cid: (float(a) if a is not None else None) for cid, a in filas}
