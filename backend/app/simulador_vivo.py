"""Simulador EN VIVO para tableros de demostración (Etapa 17).

Mientras el AcuRev real no esté enviando, permite ver el dashboard "moviéndose":
cada `simulador_vivo_segundos` agrega una medición por circuito al tablero DEMO
configurado y la avisa en tiempo real (mismo camino que usará el lector del CSV real).

- Se ACTIVA solo si el .env define SIMULADOR_VIVO_TABLERO=<id del tablero DEMO>.
  Sin ese ajuste no existe (es lo normal).
- Solo funciona en tableros cuyo código empieza con "DEMO" (mismo candado que el script).
- Reutiliza el generador de scripts/simular_mediciones.py (misma curva y mismos valores típicos).
- Marca la última comunicación del equipo, como haría un envío real a /ingesta.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Circuito, Dispositivo, Medicion
from app.servicio_mediciones import registrar_mediciones
from app.tiempo_real import canal
from scripts.simular_mediciones import _tablero_demo, generar

log = logging.getLogger("electromap.auditoria")


def un_envio(db: Session, tablero_id: int, ahora: datetime | None = None, notificar=None) -> int:
    """Agrega UNA medición por circuito (en el momento `ahora`). Devuelve cuántas guardó."""
    _tablero_demo(db, tablero_id)
    ahora = (ahora or datetime.now(timezone.utc)).replace(microsecond=0)
    intervalo = timedelta(seconds=settings.simulador_vivo_segundos)
    circuitos = db.scalars(select(Circuito).where(
        Circuito.tablero_id == tablero_id, Circuito.activo.is_(True), Circuito.dispositivo_id.is_not(None),
    ).order_by(Circuito.id)).all()

    # Cada circuito continúa su contador de energía desde la última medición.
    inicios = {}
    for c in circuitos:
        energia = db.scalar(select(Medicion.energia_kwh).where(Medicion.circuito_id == c.id)
                            .order_by(Medicion.medido_en.desc()).limit(1))
        inicios[c.id] = (ahora, float(energia or 0))

    filas = list(generar(circuitos, inicios, ahora + timedelta(seconds=1), intervalo,
                         semilla=int(ahora.timestamp())))
    for equipo_id in {c.dispositivo_id for c in circuitos}:
        db.get(Dispositivo, equipo_id).ultima_comunicacion = ahora
    return registrar_mediciones(db, filas, notificar=notificar)


def _un_envio_real() -> None:
    with SessionLocal() as db:
        un_envio(db, settings.simulador_vivo_tablero, notificar=canal.publicar_desde_hilo)


async def simular_en_vivo() -> None:
    """Bucle: un envío simulado cada `simulador_vivo_segundos` (corre en un hilo aparte)."""
    log.info("Simulador en vivo ACTIVO para el tablero %s", settings.simulador_vivo_tablero)
    while True:
        try:
            await asyncio.to_thread(_un_envio_real)
        except Exception:
            log.exception("Simulador en vivo: error (¿el tablero es DEMO y tiene circuitos con equipo?)")
        await asyncio.sleep(settings.simulador_vivo_segundos)
