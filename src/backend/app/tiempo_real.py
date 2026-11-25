"""Canal en tiempo real (Etapa 16 — Historia 004).

Lleva la cuenta de qué navegadores están mirando cada tablero (WebSocket abierto)
y les envía los eventos de ESE tablero apenas ocurren. Un navegador suscrito a un
tablero nunca recibe eventos de otro: el aislamiento por cliente se mantiene.

- `publicar(...)`            : para código asíncrono (corre en el bucle del servidor).
- `publicar_desde_hilo(...)` : para código normal (rutas `def`, vigilante), que corre
                               en otros hilos; agenda el envío en el bucle del servidor.
"""
import asyncio
from collections import defaultdict

from fastapi import WebSocket


class CanalTiempoReal:
    def __init__(self):
        self._suscriptores: dict[int, set[WebSocket]] = defaultdict(set)
        self._bucle: asyncio.AbstractEventLoop | None = None

    def iniciar(self, bucle: asyncio.AbstractEventLoop) -> None:
        """Guarda el bucle del servidor (se llama al arrancar, en main.py)."""
        self._bucle = bucle

    def suscribir(self, tablero_id: int, websocket: WebSocket) -> None:
        self._suscriptores[tablero_id].add(websocket)

    def desuscribir(self, tablero_id: int, websocket: WebSocket) -> None:
        conexiones = self._suscriptores.get(tablero_id)
        if conexiones is not None:
            conexiones.discard(websocket)
            if not conexiones:
                del self._suscriptores[tablero_id]

    def cantidad(self, tablero_id: int) -> int:
        return len(self._suscriptores.get(tablero_id, ()))

    async def publicar(self, tablero_id: int, evento: dict) -> None:
        """Envía el evento a todos los navegadores suscritos a ese tablero."""
        for websocket in list(self._suscriptores.get(tablero_id, ())):
            try:
                await websocket.send_json(evento)
            except Exception:
                # Conexión rota (navegador cerrado sin avisar): se descarta.
                self.desuscribir(tablero_id, websocket)

    def publicar_desde_hilo(self, tablero_id: int, evento: dict) -> None:
        """Igual que publicar(), pero se puede llamar desde código que no es asíncrono."""
        if self._bucle is None or self._bucle.is_closed():
            return  # servidor sin arrancar (ej. scripts): no hay a quién enviar
        asyncio.run_coroutine_threadsafe(self.publicar(tablero_id, evento), self._bucle)


canal = CanalTiempoReal()


def evento_alarma(alarma, accion: str) -> dict:
    """Convierte una alarma en el mensaje que recibe el navegador (accion: 'creada' o 'resuelta')."""
    return {
        "tipo": "alarma",
        "accion": accion,
        "alarma_id": alarma.id,
        "alarma_tipo": alarma.tipo,
        "severidad": alarma.severidad,
        "dispositivo_id": alarma.dispositivo_id,
        "circuito_id": alarma.circuito_id,
        "mensaje": alarma.mensaje,
        "generado_en": alarma.generado_en.isoformat() if alarma.generado_en else None,
        "resuelto": alarma.resuelto,
    }