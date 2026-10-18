"""Pruebas automáticas de contraseñas y tokens (no necesitan base de datos).

Ejecutar desde backend/:  pytest
"""
from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.security import crear_token, hashear_password, leer_token, verificar_password


def test_hash_no_guarda_la_password_en_texto():
    h = hashear_password("ClaveSegura123")
    assert "ClaveSegura123" not in h


def test_password_correcta_se_acepta():
    h = hashear_password("ClaveSegura123")
    assert verificar_password("ClaveSegura123", h)


def test_password_incorrecta_se_rechaza():
    h = hashear_password("ClaveSegura123")
    assert not verificar_password("otraClave", h)


def test_hash_invalido_no_rompe_y_se_rechaza():
    assert not verificar_password("lo-que-sea", "esto-no-es-un-hash")


def test_token_valido_devuelve_el_usuario():
    assert leer_token(crear_token(42)) == 42


def test_token_alterado_se_rechaza():
    token = crear_token(42)
    assert leer_token(token[:-2] + "xx") is None


def test_token_firmado_con_otra_clave_se_rechaza():
    falso = jwt.encode({"sub": "1"}, "clave-de-un-atacante-0123456789-abcdef", algorithm="HS256")
    assert leer_token(falso) is None


def test_token_expirado_se_rechaza():
    vencido = jwt.encode(
        {"sub": "42", "exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
        settings.jwt_secret,
        algorithm=settings.jwt_algoritmo,
    )
    assert leer_token(vencido) is None
