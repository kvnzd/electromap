"""Funciones de seguridad: contraseñas y tokens de sesión.

- Las contraseñas NUNCA se guardan en texto: se guarda un hash Argon2
  (algoritmo recomendado actualmente para contraseñas).
- Al iniciar sesión se entrega un token JWT firmado con JWT_SECRET.
  El token dice quién es el usuario y cuándo expira; no se puede falsificar sin la clave.
"""
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
