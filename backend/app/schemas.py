"""Formatos de entrada y salida de la API (JSON).

- *Out: lo que el backend DEVUELVE. Nunca incluye password_hash.
- *Crear / *Editar: lo que el backend ACEPTA. Los largos máximos coinciden con
  las columnas de la BBDD, así un dato inválido se rechaza con un mensaje claro
  antes de llegar a la base de datos.
"""
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Salida(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- Usuarios / autenticación ----------

class UsuarioOut(_Salida):
    id: int
    nombre_usuario: str
    rol: str
    empresa_id: int | None
    cliente_id: int | None
    puede_editar: bool
    activo: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class UsuarioCrear(BaseModel):
    nombre_usuario: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=10, max_length=128)
    rol: Literal["vsc", "empresa", "cliente"]
    empresa_id: int | None = None
    cliente_id: int | None = None
    puede_editar: bool = False


class UsuarioEditar(BaseModel):
    puede_editar: bool | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)


# ---------- Empresas ----------

class EmpresaOut(_Salida):
    id: int
    nombre: str
    rut: str | None
    contacto_email: str | None
    activo: bool


class EmpresaCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    rut: str | None = Field(default=None, max_length=12)
    contacto_email: str | None = Field(default=None, max_length=150)


class EmpresaEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    rut: str | None = Field(default=None, max_length=12)
    contacto_email: str | None = Field(default=None, max_length=150)
    activo: bool | None = None


# ---------- Clientes ----------

class ClienteOut(_Salida):
    id: int
    empresa_id: int
    nombre: str
    activo: bool


class ClienteCrear(BaseModel):
    nombre: str = Field(min_length=1, max_length=150)
    # Solo lo usa VSC. Para un usuario empresa se asigna automáticamente su propia empresa.
    empresa_id: int | None = None


class ClienteEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=150)
    activo: bool | None = None


# ---------- Sucursales ----------

class SucursalOut(_Salida):
    id: int
    cliente_id: int
    nombre: str
    direccion: str | None
    activo: bool


class SucursalCrear(BaseModel):
    cliente_id: int
    nombre: str = Field(min_length=1, max_length=100)
    direccion: str | None = Field(default=None, max_length=200)


class SucursalEditar(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    direccion: str | None = Field(default=None, max_length=200)
    activo: bool | None = None


# ---------- Tableros ----------

class TableroOut(_Salida):
    id: int
    sucursal_id: int
    codigo: str
    nombre: str
    ubicacion: str | None
    amperaje_nominal: float | None
    activo: bool


class TableroCrear(BaseModel):
    sucursal_id: int
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=100)
    ubicacion: str | None = Field(default=None, max_length=200)
    amperaje_nominal: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)


class TableroEditar(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    ubicacion: str | None = Field(default=None, max_length=200)
    amperaje_nominal: Decimal | None = Field(default=None, ge=0, max_digits=6, decimal_places=2)
    activo: bool | None = None
