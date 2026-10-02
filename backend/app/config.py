"""Configuración del backend, leída desde variables de entorno o el archivo .env.

Así la contraseña de la base de datos nunca queda escrita en el código.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Dirección de conexión a PostgreSQL (Railway). Obligatoria: si falta, el backend no arranca.
    database_url: str

    @property
    def sqlalchemy_url(self) -> str:
        """Railway entrega 'postgresql://...'; SQLAlchemy necesita indicar el driver psycopg."""
        url = self.database_url
        for prefijo in ("postgres://", "postgresql://"):
            if url.startswith(prefijo):
                return "postgresql+psycopg://" + url[len(prefijo):]
        return url


settings = Settings()
