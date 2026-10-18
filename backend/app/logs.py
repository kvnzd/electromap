"""Configuración de los registros (logs) del sistema.

- logs/seguridad.log : intentos de acceso denegados.
- logs/auditoria.log : acciones de administración (quién creó/editó qué).
La carpeta logs/ está excluida de Git. También se muestran en la terminal.
"""
import logging
from pathlib import Path

CARPETA_LOGS = Path(__file__).resolve().parent.parent / "logs"


def _configurar(nombre_logger: str, archivo: str, nivel: int) -> None:
    log = logging.getLogger(nombre_logger)
    if log.handlers:  # ya configurado (evita duplicar al recargar)
        return
    CARPETA_LOGS.mkdir(exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    a_archivo = logging.FileHandler(CARPETA_LOGS / archivo, encoding="utf-8")
    a_archivo.setFormatter(formato)
    a_consola = logging.StreamHandler()
    a_consola.setFormatter(formato)

    log.addHandler(a_archivo)
    log.addHandler(a_consola)
    log.setLevel(nivel)


def configurar_logs() -> None:
    _configurar("electromap.seguridad", "seguridad.log", logging.INFO)
    _configurar("electromap.auditoria", "auditoria.log", logging.INFO)
