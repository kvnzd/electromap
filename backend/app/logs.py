"""Configuración del registro (log) de seguridad.

Los intentos de acceso denegados se escriben en backend/logs/seguridad.log
(carpeta excluida de Git) y también se muestran en la terminal.
"""
import logging
from pathlib import Path

CARPETA_LOGS = Path(__file__).resolve().parent.parent / "logs"


def configurar_logs() -> None:
    log = logging.getLogger("electromap.seguridad")
    if log.handlers:  # ya configurado (evita duplicar al recargar)
        return
    CARPETA_LOGS.mkdir(exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    archivo = logging.FileHandler(CARPETA_LOGS / "seguridad.log", encoding="utf-8")
    archivo.setFormatter(formato)
    consola = logging.StreamHandler()
    consola.setFormatter(formato)

    log.addHandler(archivo)
    log.addHandler(consola)
    log.setLevel(logging.INFO)
