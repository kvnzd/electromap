"""Configuración de los registros (logs) del sistema.

- logs/seguridad.log : intentos de acceso denegados.
- logs/auditoria.log : acciones de administración (quién creó/editó qué).
La carpeta logs/ está excluida de Git. También se muestran en la terminal.
La carpeta se puede cambiar con LOGS_CARPETA (las pruebas usan una temporal para no
mezclar sus registros con los del sistema real).
"""
import logging

from app.config import settings


def _configurar(nombre_logger: str, archivo: str, nivel: int) -> None:
    log = logging.getLogger(nombre_logger)
    if log.handlers:  # ya configurado (evita duplicar al recargar)
        return
    carpeta = settings.logs_carpeta
    carpeta.mkdir(parents=True, exist_ok=True)
    formato = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    a_archivo = logging.FileHandler(carpeta / archivo, encoding="utf-8")
    a_archivo.setFormatter(formato)
    a_consola = logging.StreamHandler()
    a_consola.setFormatter(formato)

    log.addHandler(a_archivo)
    log.addHandler(a_consola)
    log.setLevel(nivel)


def configurar_logs() -> None:
    _configurar("electromap.seguridad", "seguridad.log", logging.INFO)
    _configurar("electromap.auditoria", "auditoria.log", logging.INFO)
