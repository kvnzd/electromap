"""WebSocket de un tablero: /ws/tableros/{tablero_id} (Etapa 16 — Historia 004).

Protocolo:
1. El navegador abre la conexión y envía como PRIMER mensaje: {"token": "<JWT de su sesión>"}.
   El token no va en la URL para que no quede escrito en los registros del servidor.
2. El servidor verifica:
   - sesión válida y cuenta habilitada; si no → cierra con código 4401;
   - que el tablero esté dentro de su ámbito; si no → cierra con 4403
     (sin decir si el tablero existe) y lo anota en logs/seguridad.log.
3. Responde {"tipo": "conectado", "tablero_id": N} y desde ahí envía los eventos de ESE tablero:
   - {"tipo": "comunicacion", ...}  un equipo del tablero envió datos;
   - {"tipo": "alarma", ...}        una alarma del tablero se creó o se resolvió;
   - (Etapa 12) {"tipo": "medicion", ...}.
"""
import asyncio

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.autorizacion import registrar_acceso_denegado, tableros_visibles
from app.db import get_db
from app.deps import cuenta_habilitada
from app.models import Tablero, Usuario
from app.security import leer_token
from app.tiempo_real import canal

router = APIRouter(tags=["tiempo real"])

ESPERA_TOKEN_SEGUNDOS = 10
NO_AUTENTICADO = 4401
SIN_ACCESO = 4403


def _verificar_acceso(db: Session, token, tablero_id: int) -> int | None:
    """Devuelve None si el usuario puede mirar el tablero; si no, el código de cierre."""
    try:
        usuario_id = leer_token(token) if isinstance(token, str) else None
        usuario = db.get(Usuario, usuario_id) if usuario_id else None
        if not cuenta_habilitada(db, usuario):
            return NO_AUTENTICADO
        if db.scalar(tableros_visibles(usuario).where(Tablero.id == tablero_id)) is None:
            registrar_acceso_denegado(usuario, f"tiempo real del tablero {tablero_id}")
            return SIN_ACCESO
        return None
    finally:
        # Termina la consulta y libera la conexión a la BBDD: el WebSocket puede durar horas
        # y no debe mantener ocupada una conexión mientras tanto.
        db.commit()


@router.websocket("/ws/tableros/{tablero_id}")
async def tablero_en_vivo(websocket: WebSocket, tablero_id: int, db: Session = Depends(get_db)):
    await websocket.accept()

    # 1) Primer mensaje: el token de la sesión (con tiempo límite).
    try:
        mensaje = await asyncio.wait_for(websocket.receive_json(), ESPERA_TOKEN_SEGUNDOS)
        token = mensaje.get("token") if isinstance(mensaje, dict) else None
    except WebSocketDisconnect:
        return
    except (asyncio.TimeoutError, ValueError, KeyError):
        await websocket.close(code=NO_AUTENTICADO)
        return

    # 2) Permisos (consulta a la BBDD en un hilo aparte para no bloquear el servidor).
    codigo = await run_in_threadpool(_verificar_acceso, db, token, tablero_id)
    if codigo is not None:
        await websocket.close(code=codigo)
        return

    # 3) Suscrito: desde ahora recibe los eventos de este tablero.
    canal.suscribir(tablero_id, websocket)
    try:
        await websocket.send_json({"tipo": "conectado", "tablero_id": tablero_id})
        # Mantiene la conexión abierta; lo que envíe el navegador se ignora.
        while (await websocket.receive())["type"] != "websocket.disconnect":
            pass
    except WebSocketDisconnect:
        pass
    finally:
        canal.desuscribir(tablero_id, websocket)