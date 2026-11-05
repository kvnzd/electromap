"""Guardar mediciones y avisarlas en tiempo real (Etapa 17).

Es el ÚNICO camino por el que una medición entra a la base y llega al dashboard:
lo usa hoy el simulador en vivo (tableros DEMO) y lo usará el lector del CSV real
del AcuRev (Etapa 12), sin cambios.

- Inserta las filas; las que ya existían (mismo circuito y momento) se omiten.
- Después de guardar (commit), avisa cada medición NUEVA a quienes miran su tablero:
  {"tipo": "medicion", "circuito_id": ..., "medido_en": ..., "voltaje_a": ..., ...}
"""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Circuito, Medicion

CAMPOS = ("voltaje_a", "voltaje_b", "voltaje_c", "corriente_a", "corriente_b", "corriente_c",
          "potencia_activa", "energia_kwh", "temperatura_tablero")


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

    if notificar and nuevas:
        claves = {(n.circuito_id, n.medido_en) for n in nuevas}
        ids = {c for c, _ in claves}
        tablero_de = dict(db.execute(select(Circuito.id, Circuito.tablero_id).where(Circuito.id.in_(ids))).all())
        for fila in filas:
            if (fila["circuito_id"], fila["medido_en"]) in claves:
                notificar(tablero_de[fila["circuito_id"]], evento_medicion(fila))
    return len(nuevas)
