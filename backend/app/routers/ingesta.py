"""Receptor de datos del AcuRev (Etapa 11 — Historia 003).

El AcuRev envía sus mediciones por HTTP POST a este endpoint. En esta etapa
el receptor funciona como REGISTRADOR: valida la clave del equipo, actualiza
`ultima_comunicacion` y guarda cada envío tal como llega (sin interpretarlo),
para conocer el formato real del CSV. La interpretación es la Etapa 12.

Autenticación (sin usuario ni JWT: quien llama es una máquina):
- Basic:  usuario cualquiera, contraseña = clave de ingesta "em_..."
- Bearer: cabecera "Authorization: Bearer em_..."
La clave se convierte a hash SHA-256 y se busca en dispositivos.token_ingesta.
"""
import base64
import binascii
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Dispositivo
from app.security import hashear_clave_ingesta

router = APIRouter(prefix="/ingesta", tags=["ingesta (equipos AcuRev)"])

log_seguridad = logging.getLogger("electromap.seguridad")

# 401 con desafío "Basic": algunos equipos solo envían usuario/clave
# después de recibir este desafío del servidor.
_NO_AUTORIZADO = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Clave de ingesta inválida o ausente",
    headers={"WWW-Authenticate": 'Basic realm="electromap-ingesta"'},
)


def _extraer_clave(request: Request) -> str | None:
    """Obtiene la clave desde la cabecera Authorization (Basic o Bearer)."""
    tipo, _, valor = request.headers.get("Authorization", "").partition(" ")
    tipo, valor = tipo.lower(), valor.strip()
    if tipo == "bearer":
        return valor or None
    if tipo == "basic":
        try:
            texto = base64.b64decode(valor, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
        _usuario, separador, clave = texto.partition(":")
        return clave if separador and clave else None
    return None


def _equipo_autenticado(request: Request, db: Session) -> Dispositivo:
    """Devuelve el equipo dueño de la clave, o responde 401 y lo registra."""
    origen = request.client.host if request.client else "desconocido"
    clave = _extraer_clave(request)
    equipo = None
    if clave:
        equipo = db.scalar(
            select(Dispositivo).where(Dispositivo.token_ingesta == hashear_clave_ingesta(clave))
        )
    if equipo is None or not equipo.activo:
        log_seguridad.warning("INGESTA RECHAZADA desde %s: clave inválida, ausente o equipo inactivo", origen)
        raise _NO_AUTORIZADO
    return equipo


async def _leer_cuerpo(request: Request) -> bytes:
    """Lee el cuerpo crudo respetando el tamaño máximo (413 si se excede)."""
    demasiado_grande = HTTPException(
        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
        detail=f"El envío supera el máximo de {settings.ingesta_max_bytes} bytes",
    )
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > settings.ingesta_max_bytes:
        raise demasiado_grande
    cuerpo = await request.body()
    if len(cuerpo) > settings.ingesta_max_bytes:
        raise demasiado_grande
    return cuerpo


@router.post("")
def recibir_envio(
    request: Request,
    cuerpo: bytes = Depends(_leer_cuerpo),
    db: Session = Depends(get_db),
):
    """Recibe un envío del AcuRev, lo guarda tal cual y marca la última comunicación."""
    equipo = _equipo_autenticado(request, db)
    ahora = datetime.now(timezone.utc)

    archivo = None
    if cuerpo:  # un POST vacío (prueba de conexión) solo actualiza la última comunicación
        carpeta = settings.ingesta_carpeta / f"dispositivo_{equipo.id}"
        carpeta.mkdir(parents=True, exist_ok=True)
        archivo = ahora.strftime("%Y%m%dT%H%M%S_%fZ")
        (carpeta / f"{archivo}_cuerpo.txt").write_bytes(cuerpo)
        # Cabeceras para conocer el formato (tipo de contenido, etc.). NUNCA se guarda la clave.
        cabeceras = "\n".join(
            f"{k}: {v}" for k, v in request.headers.items() if k.lower() != "authorization"
        )
        (carpeta / f"{archivo}_cabeceras.txt").write_text(cabeceras, encoding="utf-8")

    equipo.ultima_comunicacion = ahora
    db.commit()
    return {"recibido": True, "dispositivo_id": equipo.id, "bytes": len(cuerpo), "archivo": archivo}
    