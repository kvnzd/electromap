"""Cambia la contraseña de un usuario existente (por ejemplo, si se olvidó).

Uso (desde la carpeta backend/, con el entorno virtual activado):
    python -m scripts.cambiar_password

La nueva contraseña no se muestra al escribirla y se guarda como hash.
OJO: este script ACTUALIZA una fila de la tabla usuarios. No crea ni modifica tablas.
"""
from getpass import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Usuario
from app.security import hashear_password


def main() -> None:
    print("=== Cambiar contraseña ElectroMap ===")
    nombre = input("Nombre de usuario: ").strip()

    with SessionLocal() as db:
        usuario = db.scalar(select(Usuario).where(Usuario.nombre_usuario == nombre))
        if usuario is None:
            raise SystemExit(f"No existe un usuario llamado '{nombre}'.")

        password = getpass("Nueva contraseña (mín. 10 caracteres): ")
        if len(password) < 10:
            raise SystemExit("La contraseña debe tener al menos 10 caracteres.")
        if password != getpass("Repetir nueva contraseña: "):
            raise SystemExit("Las contraseñas no coinciden.")

        usuario.password_hash = hashear_password(password)
        db.commit()
        print(f"Contraseña de '{nombre}' actualizada.")


if __name__ == "__main__":
    main()
