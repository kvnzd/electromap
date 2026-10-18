"""Crea un usuario en la base de datos (por ejemplo, el primer administrador VSC).

Uso (desde la carpeta backend/, con el entorno virtual activado):
    python -m scripts.crear_usuario

Pide los datos por pantalla. La contraseña no se muestra al escribirla
y se guarda como hash (nunca en texto plano).

OJO: este script INSERTA una fila en la tabla usuarios de la base de datos
configurada en .env. No crea ni modifica tablas.
"""
from getpass import getpass

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Usuario
from app.security import hashear_password

ROLES = ("vsc", "empresa", "cliente")


def pedir(texto: str, opcional: bool = False) -> str | None:
    valor = input(texto).strip()
    if not valor and not opcional:
        raise SystemExit("Dato obligatorio. Cancelado.")
    return valor or None


def main() -> None:
    print("=== Crear usuario ElectroMap ===")
    nombre = pedir("Nombre de usuario: ")
    rol = pedir(f"Rol {ROLES}: ")
    if rol not in ROLES:
        raise SystemExit(f"Rol inválido. Debe ser uno de {ROLES}.")

    empresa_id = cliente_id = None
    puede_editar = False
    if rol == "vsc":
        puede_editar = True
    elif rol == "empresa":
        empresa_id = int(pedir("ID de la empresa: "))
        puede_editar = (pedir("¿Puede editar? (s/n): ") or "n").lower() == "s"
    else:  # cliente: nunca edita (regla del negocio y constraint de la BBDD)
        cliente_id = int(pedir("ID del cliente: "))

    password = getpass("Contraseña (mín. 10 caracteres): ")
    if len(password) < 10:
        raise SystemExit("La contraseña debe tener al menos 10 caracteres.")
    if password != getpass("Repetir contraseña: "):
        raise SystemExit("Las contraseñas no coinciden.")

    with SessionLocal() as db:
        if db.scalar(select(Usuario).where(Usuario.nombre_usuario == nombre)):
            raise SystemExit(f"Ya existe un usuario llamado '{nombre}'.")
        usuario = Usuario(
            nombre_usuario=nombre,
            password_hash=hashear_password(password),
            rol=rol,
            empresa_id=empresa_id,
            cliente_id=cliente_id,
            puede_editar=puede_editar,
        )
        db.add(usuario)
        db.commit()
        print(f"Usuario '{nombre}' creado con id {usuario.id} (rol {rol}).")


if __name__ == "__main__":
    main()
