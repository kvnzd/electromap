"""Receptor de datos del AcuRev (Etapas 11 y 12 — Historia 003).

El AcuRev envía sus mediciones por HTTP POST a este endpoint. Por cada envío:
1. Valida la clave del equipo y actualiza `ultima_comunicacion`.
2. Guarda el envío tal como llega (registro crudo, útil para revisar el formato).
3. Etapa 12: lee el CSV (app/lector_csv.py) y guarda las mediciones de cada circuito
   del equipo según su `canal_acurev`, por el mismo camino que el resto del sistema
   (servicio_mediciones: sin duplicados, alarmas y aviso en tiempo real).
Si el CSV no se puede leer, responde 200 igual (el envío quedó guardado) y lo informa
en "avisos": reintentarlo no lo arreglaría. Si falla la base de datos, responde 500
y el AcuRev lo reenvía; los duplicados se descartan.

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
from app.lector_csv import FormatoInvalido, extraer_csv, leer_filas, mediciones_del_envio
from app.models import Circuito, Dispositivo
from app.security import hashear_clave_ingesta
from app.servicio_mediciones import registrar_mediciones
from app.tiempo_real import canal

router = APIRouter(prefix="/ingesta", tags=["ingesta (equipos AcuRev)"])

log_seguridad = logging.getLogger("electromap.seguridad")
log_auditoria = logging.getLogger("electromap.auditoria")

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


def _leer_mediciones(db: Session, equipo: Dispositivo, cuerpo: bytes, content_type: str) -> dict:
    """Etapa 12: CSV del envío → mediciones guardadas. Devuelve el resumen para la respuesta."""
    try:
        filas = [f for _, texto in extraer_csv(cuerpo, content_type) for f in leer_filas(texto)]
    except FormatoInvalido as error:
        log_auditoria.warning("INGESTA dispositivo_id=%s: CSV no legible (%s)", equipo.id, error)
        return {"filas_csv": 0, "mediciones_nuevas": 0, "avisos": [str(error)]}

    circuitos = db.scalars(
        select(Circuito).where(Circuito.dispositivo_id == equipo.id, Circuito.activo,
                               Circuito.canal_acurev.is_not(None))
    ).all()
    mediciones, avisos = mediciones_del_envio(filas, equipo.id, circuitos)
    nuevas = registrar_mediciones(db, mediciones, canal.publicar_desde_hilo)
    for aviso in avisos:
        log_auditoria.warning("INGESTA dispositivo_id=%s: %s", equipo.id, aviso)
    log_auditoria.info("INGESTA dispositivo_id=%s: %s filas, %s mediciones nuevas",
                       equipo.id, len(filas), nuevas)
    return {"filas_csv": len(filas), "mediciones_nuevas": nuevas, "avisos": avisos}


@router.post("")
def recibir_envio(
    request: Request,
    cuerpo: bytes = Depends(_leer_cuerpo),
    db: Session = Depends(get_db),
):
    """Recibe un envío del AcuRev: lo guarda tal cual, marca la comunicación y lee el CSV."""
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
    tablero_id = equipo.tablero_id
    db.commit()
    # Aviso en tiempo real a quienes estén mirando el tablero de este equipo.
    canal.publicar_desde_hilo(tablero_id, {
        "tipo": "comunicacion", "dispositivo_id": equipo.id, "en": ahora.isoformat(), "bytes": len(cuerpo),
    })

    resumen = {"filas_csv": 0, "mediciones_nuevas": 0, "avisos": []}
    if cuerpo:
        resumen = _leer_mediciones(db, equipo, cuerpo, request.headers.get("content-type", ""))
    return {"recibido": True, "dispositivo_id": equipo.id, "bytes": len(cuerpo), "archivo": archivo, **resumen}
    