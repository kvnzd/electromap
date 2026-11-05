"""Configuración del backend, leída desde variables de entorno o el archivo .env.

Así las contraseñas y claves nunca quedan escritas en el código.
"""
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Dirección de conexión a PostgreSQL (Railway). Obligatoria.
    database_url: str

    # Clave para firmar los tokens de sesión. Obligatoria y de al menos 32 caracteres.
    jwt_secret: str = Field(min_length=32)
    jwt_algoritmo: str = "HS256"
    jwt_expira_minutos: int = 480

    # Base de datos SOLO para pruebas automáticas (pytest). Debe ser distinta de la real.
    # Si no está configurada, las pruebas que necesitan base de datos se omiten.
    test_database_url: str | None = None

    # Direcciones web (frontend) autorizadas para llamar a esta API desde el navegador (CORS).
    cors_origenes: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    # Ingesta del AcuRev (Etapa 11): carpeta donde se guarda cada envío tal como llega
    # (registrador temporal para conocer el formato real; excluida de Git).
    ingesta_carpeta: Path = Path(__file__).resolve().parent.parent / "ingesta_recibida"
    # Tamaño máximo aceptado por envío (bytes). Protege el disco ante envíos abusivos.
    ingesta_max_bytes: int = 5_000_000
    
    # Vigilante de equipos desconectados (Etapa 13).
    # Cada cuántos segundos revisa y cuántos minutos sin datos cuentan como "desconectado".
    vigilante_activo: bool = True
    vigilante_intervalo_segundos: int = 60
    offline_minutos: int = 5

    # Simulador en vivo para el dashboard (Etapa 17). Vacío = apagado (lo normal).
    # Para activarlo: SIMULADOR_VIVO_TABLERO=<id de un tablero DEMO> en el .env.
    simulador_vivo_tablero: int | None = None
    simulador_vivo_segundos: int = 5
    
    @property
    def sqlalchemy_url(self) -> str:
        return a_url_sqlalchemy(self.database_url)


def a_url_sqlalchemy(url: str) -> str:
    """Railway entrega 'postgresql://...'; SQLAlchemy necesita indicar el driver psycopg."""
    for prefijo in ("postgres://", "postgresql://"):
        if url.startswith(prefijo):
            return "postgresql+psycopg://" + url[len(prefijo):]
    return url


settings = Settings()
