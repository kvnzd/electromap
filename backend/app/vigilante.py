"""Vigilante de equipos desconectados (Etapa 13 — Historia 003).

Cada minuto revisa la última comunicación de cada AcuRev activo:
- Lleva más de `offline_minutos` sin enviar datos y no tiene ya una alarma
  'dispositivo_offline' abierta → crea una (severidad crítica).
- Volvió a comunicarse y tenía esa alarma abierta → la marca resuelta sola
  (resuelto_por queda vacío: la resolvió el sistema, no una persona).
Un equipo que nunca se ha comunicado (recién registrado) no cuenta como desconectado.

Nota: el vigilante corre dentro del proceso del backend. Debe haber UN solo proceso
(uvicorn sin varios workers); si hubiera varios, cada uno revisaría por su cuenta.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Alarma, Dispositivo

TIPO_OFFLINE = "dispositivo_offline"
log = logging.getLogger("electromap.auditoria")


def _alarma_abierta(db: Session, dispositivo_id: int) -> Alarma | None:
    return db.scalar(select(Alarma).where(
        Alarma.dispositivo_id == dispositivo_id,
        Alarma.tipo == TIPO_OFFLINE,
        Alarma.resuelto.is_(False),
    ))


def revisar_equipos(db: Session, ahora: datetime | None = None) -> dict:
    """Crea o resuelve alarmas de equipo desconectado. Devuelve cuántas creó y resolvió."""
    ahora = ahora or datetime.now(timezone.utc)
    limite = ahora - timedelta(minutes=settings.offline_minutos)
    creadas = resueltas = 0

    equipos = db.scalars(select(Dispositivo).where(
        Dispositivo.activo.is_(True),
        Dispositivo.ultima_comunicacion.is_not(None),
    )).all()

    for equipo in equipos:
        abierta = _alarma_abierta(db, equipo.id)
        desconectado = equipo.ultima_comunicacion < limite

        if desconectado and abierta is None:
            minutos = int((ahora - equipo.ultima_comunicacion).total_seconds() // 60)
            db.add(Alarma(
                dispositivo_id=equipo.id,
                tipo=TIPO_OFFLINE,
                severidad="critica",
                valor_medido=Decimal(min(minutos, 99_999_999)),  # minutos sin datos
                valor_umbral=Decimal(settings.offline_minutos),
                mensaje=f"Equipo sin enviar datos hace {minutos} min (límite {settings.offline_minutos} min)",
            ))
            creadas += 1
            log.warning("ALARMA %s: dispositivo %s sin datos hace %s min", TIPO_OFFLINE, equipo.id, minutos)

        elif not desconectado and abierta is not None:
            abierta.resuelto = True
            abierta.resuelto_en = ahora
            resueltas += 1
            log.info("ALARMA %s resuelta: dispositivo %s volvió a comunicarse", TIPO_OFFLINE, equipo.id)

    db.commit()
    return {"creadas": creadas, "resueltas": resueltas}


def _una_revision() -> dict:
    """Abre su propia sesión de base de datos (no depende de ninguna petición HTTP)."""
    with SessionLocal() as db:
        return revisar_equipos(db)


async def vigilar() -> None:
    """Bucle infinito: revisa, espera el intervalo y vuelve a revisar."""
    while True:
        try:
            # La revisión usa la base de datos (operación bloqueante): se ejecuta en un hilo aparte
            # para no congelar el servidor mientras tanto.
            await asyncio.to_thread(_una_revision)
        except Exception:
            # Un error (ej. la base no responde) se registra, pero el vigilante sigue funcionando.
            log.exception("Vigilante: error al revisar equipos")
        await asyncio.sleep(settings.vigilante_intervalo_segundos)