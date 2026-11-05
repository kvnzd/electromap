from datetime import date, datetime
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
# ---------- Dispositivos (analizadores AcuRev) ----------

class DispositivoOut(_Salida):
    id: int
    tablero_id: int
    modelo: str
    numero_serie: str | None
    direccion_ip: str | None
    fecha_instalacion: date | None
    ultima_comunicacion: datetime | None   # última vez que el equipo envió datos
    activo: bool
    # OJO: token_ingesta (el hash de la clave) NO se incluye nunca.


class DispositivoConClave(DispositivoOut):
    """Respuesta especial al registrar el equipo o regenerar su clave.
    La clave se muestra UNA sola vez: después no se puede recuperar, solo regenerar."""
    clave_ingesta: str


class DispositivoCrear(BaseModel):
    tablero_id: int
    modelo: str = Field(default="AcuRev-2110", min_length=1, max_length=50)
    numero_serie: str | None = Field(default=None, max_length=50)
    direccion_ip: str | None = Field(default=None, max_length=45)
    fecha_instalacion: date | None = None


class DispositivoEditar(BaseModel):
    # tablero_id no se edita: si el equipo cambia de tablero, se desactiva y se registra de nuevo.
    modelo: str | None = Field(default=None, min_length=1, max_length=50)
    numero_serie: str | None = Field(default=None, max_length=50)
    direccion_ip: str | None = Field(default=None, max_length=45)
    fecha_instalacion: date | None = None
    activo: bool | None = None


# ---------- Circuitos ----------

class CircuitoOut(_Salida):
    id: int
    tablero_id: int
    dispositivo_id: int | None
    codigo: str
    nombre: str
    canal_acurev: str | None          # cómo identifica el AcuRev a este circuito en su CSV
    calibre_cable_mm2: float | None
    corriente_automatico: float | None
    activo: bool


class CircuitoCrear(BaseModel):
    tablero_id: int
    dispositivo_id: int | None = None
    codigo: str = Field(min_length=1, max_length=20)          # código del plano, ej. "C-01"
    nombre: str = Field(min_length=1, max_length=100)
    canal_acurev: str | None = Field(default=None, min_length=1, max_length=30)
    calibre_cable_mm2: Decimal | None = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    corriente_automatico: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)


class CircuitoEditar(BaseModel):
    # tablero_id no se edita. El dispositivo y el canal sí (recableado en terreno).
    dispositivo_id: int | None = None
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    canal_acurev: str | None = Field(default=None, min_length=1, max_length=30)
    calibre_cable_mm2: Decimal | None = Field(default=None, gt=0, max_digits=5, decimal_places=2)
    corriente_automatico: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    activo: bool | None = None

    # ---------- Historial de mediciones (Etapa 18) ----------

class PuntoHistorial(BaseModel):
    """Promedio de las mediciones de un circuito dentro de un intervalo de tiempo."""
    t: datetime  # inicio del intervalo (UTC)
    voltaje_a: float | None = None
    voltaje_b: float | None = None
    voltaje_c: float | None = None
    corriente_a: float | None = None
    corriente_b: float | None = None
    corriente_c: float | None = None
    potencia_activa: float | None = None


class ResumenCircuito(BaseModel):
    corriente_max: float | None = None   # mayor corriente medida en cualquier fase
    potencia_max: float | None = None
    energia_kwh: float | None = None     # consumo del período (lectura final − inicial del contador)


class CircuitoHistorial(BaseModel):
    id: int
    codigo: str
    nombre: str
    resumen: ResumenCircuito
    puntos: list[PuntoHistorial]


class HistorialOut(BaseModel):
    tablero_id: int
    desde: datetime
    hasta: datetime
    intervalo_segundos: int  # tamaño de cada punto del gráfico
    hay_datos: bool
    circuitos: list[CircuitoHistorial]


# ---------- Estado actual de un tablero: dashboard (Etapa 17) ----------

class UltimaMedicion(BaseModel):
    medido_en: datetime
    voltaje_a: float | None = None
    voltaje_b: float | None = None
    voltaje_c: float | None = None
    corriente_a: float | None = None
    corriente_b: float | None = None
    corriente_c: float | None = None
    potencia_activa: float | None = None
    energia_kwh: float | None = None


class CircuitoEstado(BaseModel):
    id: int
    codigo: str
    nombre: str
    dispositivo_id: int | None
    corriente_automatico: float | None
    ultima: UltimaMedicion | None  # None = el circuito aún no tiene mediciones


class EquipoEstado(BaseModel):
    id: int
    modelo: str
    numero_serie: str | None
    ultima_comunicacion: datetime | None


class AlarmaAbierta(BaseModel):
    id: int
    tipo: str
    severidad: str
    dispositivo_id: int
    circuito_id: int | None
    mensaje: str | None
    generado_en: datetime


class EstadoTableroOut(BaseModel):
    tablero_id: int
    codigo: str
    nombre: str
    equipos: list[EquipoEstado]
    circuitos: list[CircuitoEstado]
    alarmas_abiertas: list[AlarmaAbierta]
