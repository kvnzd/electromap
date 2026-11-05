"""Carga mediciones SIMULADAS en un tablero de demostración (Etapa 18).

Sirve para ver el historial y el dashboard funcionando antes de tener datos
reales del AcuRev, y como respaldo para la presentación.

Uso (desde backend/, con el entorno virtual activado):
    python -m scripts.simular_mediciones --tablero 5 --dias 3
    python -m scripts.simular_mediciones --tablero 5 --borrar     (elimina las simuladas)

Reglas de seguridad:
- SOLO funciona en tableros cuyo código empieza con "DEMO" (ej. DEMO-01), para que
  nunca se mezclen datos inventados con los de un tablero real.
- Cada circuito del tablero necesita un equipo asignado (la tabla lo exige).
- Un circuito cuyo código o nombre contiene "TRI" se simula trifásico; el resto, monofásico (fase A).
- Se puede ejecutar varias veces: las mediciones que ya existen no se duplican.

OJO: INSERTA (o borra) filas en la tabla mediciones de la base configurada en .env.
No crea ni modifica tablas.
"""
import argparse
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Circuito, Medicion, Tablero

PREFIJO_DEMO = "DEMO"
VOLTAJE_NOMINAL = 220.0   # fase-neutro en Chile
FACTOR_POTENCIA = 0.92
LOTE = 1000


def _tablero_demo(db: Session, tablero_id: int) -> Tablero:
    tablero = db.get(Tablero, tablero_id)
    if tablero is None:
        raise ValueError(f"No existe el tablero {tablero_id}")
    if not tablero.codigo.upper().startswith(PREFIJO_DEMO):
        raise ValueError(f"El tablero {tablero.codigo} no es de demostración: su código debe empezar con '{PREFIJO_DEMO}'")
    return tablero


def _es_trifasico(circuito: Circuito) -> bool:
    return "TRI" in f"{circuito.codigo} {circuito.nombre}".upper()


def _corriente(base: float, momento: datetime, azar: random.Random) -> float:
    """Más consumo de día (curva suave con máximo ~15:00 hora Chile) + ruido."""
    hora_chile = (momento.hour - 3) % 24 + momento.minute / 60
    dia = 0.35 + 0.65 * max(0.0, math.sin(math.pi * (hora_chile - 6) / 18))
    return max(0.0, base * dia * azar.uniform(0.9, 1.1))


def generar(circuitos: list[Circuito], desde: datetime, hasta: datetime, cada: timedelta):
    """Genera las filas (diccionarios) de mediciones simuladas para cada circuito."""
    for circuito in circuitos:
        azar = random.Random(circuito.id)  # misma semilla → mismos datos al repetir
        base = float(circuito.corriente_automatico) * 0.45 if circuito.corriente_automatico else 8.0
        fases = ("a", "b", "c") if _es_trifasico(circuito) else ("a",)
        energia = 0.0
        momento = desde
        while momento < hasta:
            # Todas las filas llevan las mismas columnas (las fases que no existen van vacías):
            # el insert por lotes usa las columnas de la primera fila para todo el lote.
            fila = {"dispositivo_id": circuito.dispositivo_id, "circuito_id": circuito.id, "medido_en": momento,
                    **{f"{v}_{f}": None for v in ("voltaje", "corriente") for f in ("a", "b", "c")}}
            potencia = 0.0
            for fase in fases:
                voltaje = VOLTAJE_NOMINAL * azar.uniform(0.97, 1.03)
                corriente = _corriente(base, momento, azar)
                fila[f"voltaje_{fase}"] = round(voltaje, 2)
                fila[f"corriente_{fase}"] = round(corriente, 2)
                potencia += voltaje * corriente * FACTOR_POTENCIA
            energia += potencia / 1000 * cada.total_seconds() / 3600
            fila["potencia_activa"] = round(potencia, 2)
            fila["energia_kwh"] = round(energia, 3)
            yield fila
            momento += cada


def simular(db: Session, tablero_id: int, dias: float, cada_minutos: int = 1,
            ahora: datetime | None = None) -> int:
    """Inserta las mediciones simuladas. Devuelve cuántas filas NUEVAS insertó."""
    _tablero_demo(db, tablero_id)
    circuitos = db.scalars(select(Circuito).where(
        Circuito.tablero_id == tablero_id, Circuito.activo.is_(True), Circuito.dispositivo_id.is_not(None),
    ).order_by(Circuito.id)).all()
    if not circuitos:
        raise ValueError("El tablero no tiene circuitos activos con equipo asignado")

    hasta = (ahora or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    desde = hasta - timedelta(days=dias)
    insertadas, lote = 0, []
    for fila in generar(circuitos, desde, hasta, timedelta(minutes=cada_minutos)):
        lote.append(fila)
        if len(lote) == LOTE:
            insertadas += _insertar(db, lote)
            lote = []
    if lote:
        insertadas += _insertar(db, lote)
    db.commit()
    return insertadas


def _insertar(db: Session, filas: list[dict]) -> int:
    # Si ya existe una medición de ese circuito en ese minuto, se omite (no duplica).
    nuevas = db.execute(insert(Medicion).values(filas).on_conflict_do_nothing(
        index_elements=["circuito_id", "medido_en"]).returning(Medicion.id)).all()
    return len(nuevas)


def borrar(db: Session, tablero_id: int) -> int:
    """Elimina TODAS las mediciones del tablero de demostración. Devuelve cuántas borró."""
    _tablero_demo(db, tablero_id)
    ids = select(Circuito.id).where(Circuito.tablero_id == tablero_id)
    resultado = db.execute(delete(Medicion).where(Medicion.circuito_id.in_(ids)))
    db.commit()
    return resultado.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description="Mediciones simuladas para un tablero DEMO")
    parser.add_argument("--tablero", type=int, required=True, help="id del tablero (código DEMO-...)")
    parser.add_argument("--dias", type=float, default=3, help="días hacia atrás desde ahora (por defecto 3)")
    parser.add_argument("--cada", type=int, default=1, help="minutos entre mediciones (por defecto 1)")
    parser.add_argument("--borrar", action="store_true", help="eliminar las mediciones del tablero")
    args = parser.parse_args()

    with SessionLocal() as db:
        try:
            if args.borrar:
                print(f"Mediciones eliminadas: {borrar(db, args.tablero)}")
            else:
                print(f"Mediciones nuevas: {simular(db, args.tablero, args.dias, args.cada)}")
        except ValueError as error:
            raise SystemExit(f"No se hizo nada: {error}")


if __name__ == "__main__":
    main()