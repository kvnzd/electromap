"""Configuración del backend, leída desde variables de entorno o el archivo .env.

Así las contraseñas y claves nunca quedan escritas en el código.
"""
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

    @property
    def sqlalchemy_url(self) -> str:
        """Railway entrega 'postgresql://...'; SQLAlchemy necesita indicar el driver psycopg."""
        url = self.database_url
        for prefijo in ("postgres://", "postgresql://"):
            if url.startswith(prefijo):
                return "postgresql+psycopg://" + url[len(prefijo):]
        return url


settings = Settings()
