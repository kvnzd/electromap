import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config import settings

_hasher = PasswordHash.recommended()


def hashear_password(password: str) -> str:
    """Convierte una contraseña en un hash irreversible para guardarlo en la BBDD."""
    return _hasher.hash(password)


def verificar_password(password: str, password_hash: str) -> bool:
    """Compara una contraseña escrita con el hash guardado."""
    try:
        return _hasher.verify(password, password_hash)
    except Exception:
        # Hash con formato inválido o desconocido: se trata como contraseña incorrecta.
        return False


def crear_token(usuario_id: int) -> str:
    """Genera el token de sesión para un usuario."""
    ahora = datetime.now(timezone.utc)
    payload = {
        "sub": str(usuario_id),
        "iat": ahora,
        "exp": ahora + timedelta(minutes=settings.jwt_expira_minutos),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algoritmo)


def leer_token(token: str) -> int | None:
    """Devuelve el id del usuario si el token es válido y no expiró; si no, None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algoritmo])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
# ---------- Clave de ingesta de los equipos (AcuRev) ----------

def generar_clave_ingesta() -> str:
    """Crea una clave aleatoria para un equipo AcuRev.

    Se muestra UNA sola vez al registrar el equipo (o al regenerarla).
    El prefijo "em_" ayuda a reconocerla como clave de ElectroMap.
    """
    return "em_" + secrets.token_urlsafe(32)


def hashear_clave_ingesta(clave: str) -> str:
    """Hash SHA-256 de la clave: 64 caracteres. Es lo que se guarda en dispositivos.token_ingesta."""
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()