"""Guardar mediciones y avisarlas en tiempo real (Etapa 17).

Es el ÚNICO camino por el que una medición entra a la base y llega al dashboard:
lo usa hoy el simulador en vivo (tableros DEMO) y lo usará el lector del CSV real
del AcuRev (Etapa 12), sin cambios.

- Inserta las filas; las que ya existían (mismo circuito y momento) se omiten.
- Después de guardar (commit), avisa cada medición NUEVA a quienes miran su tablero:
  {"tipo": "medicion", "circuito_id": ..., "medido_en": ..., "voltaje_a": ..., ...}
- Las mediciones nuevas pasan por el motor de alarmas (Etapa 14), que crea o resuelve
  alarmas por umbral; esas alarmas también se avisan (tipo "alarma").
"""
import logging

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Circuito, Medicion
from app.motor_alarmas import evaluar_mediciones
from app.tiempo_real import evento_alarma

CAMPOS = ("voltaje_a", "voltaje_b", "voltaje_c", "corriente_a", "corriente_b", "corriente_c",
          "potencia_activa", "energia_kwh", "temperatura_tablero")
log = logging.getLogger("electromap.auditoria")


def _numero(valor):
    return None if valor is None else round(float(valor), 3)


def evento_medicion(fila) -> dict:
    """Mensaje que recibe el navegador por cada medición (fila: objeto o diccionario)."""
    leer = (lambda c: fila.get(c)) if isinstance(fila, dict) else (lambda c: getattr(fila, c))
    return {
        "tipo": "medicion",
        "circuito_id": leer("circuito_id"),
        "dispositivo_id": leer("dispositivo_id"),
        "medido_en": leer("medido_en").isoformat(),
        **{c: _numero(leer(c)) for c in CAMPOS},
    }


def registrar_mediciones(db: Session, filas: list[dict], notificar=None) -> int:
    """Guarda las mediciones y avisa las nuevas. Devuelve cuántas eran nuevas.

    notificar(tablero_id, evento): opcional (en el servidor: canal.publicar_desde_hilo).
    """
    if not filas:
        return 0
    # Todas las filas con las mismas columnas: el insert por lotes usa las de la primera fila.
    columnas = ("dispositivo_id", "circuito_id", "medido_en", *CAMPOS)
    filas = [{c: f.get(c) for c in columnas} for f in filas]
    nuevas = db.execute(
        insert(Medicion).values(filas)
        .on_conflict_do_nothing(index_elements=["circuito_id", "medido_en"])
        .returning(Medicion.circuito_id, Medicion.medido_en)
    ).all()
    db.commit()
    if not nuevas:
        return 0
    claves = {(n.circuito_id, n.medido_en) for n in nuevas}
    filas_nuevas = [f for f in filas if (f["circuito_id"], f["medido_en"]) in claves]

    # Motor de alarmas: si falla, las mediciones ya quedaron guardadas igual.
    try:
        eventos = evaluar_mediciones(db, filas_nuevas)
        db.commit()
    except Exception:
        db.rollback()
        log.exception("Motor de alarmas: error al revisar mediciones")
        eventos = []

    if notificar:
        ids = {f["circuito_id"] for f in filas_nuevas}
        tablero_de = dict(db.execute(select(Circuito.id, Circuito.tablero_id).where(Circuito.id.in_(ids))).all())
        for fila in filas_nuevas:
            notificar(tablero_de[fila["circuito_id"]], evento_medicion(fila))
        for tablero_id, alarma, accion in eventos:
            notificar(tablero_id, evento_alarma(alarma, accion))
    return len(nuevas)
