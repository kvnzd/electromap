"""Modelos SQLAlchemy que REFLEJAN el schema existente en Railway (11 tablas).

Solo describen las tablas para poder consultarlas/insertar filas.
No se usan para crear ni alterar tablas. Si algo aquí no calza con la BBDD,
el cambio se pide en el chat de base de datos, no se "arregla" desde el código.

Soft delete: nunca DELETE; usar activo = False.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, FetchedValue, ForeignKey, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def db_default(*args, **kw):
    """Columna con DEFAULT definido en la BBDD: el ORM la omite en el INSERT
    y deja que PostgreSQL ponga el valor (now(), TRUE, 'moderada', etc.)."""
    return mapped_column(*args, server_default=FetchedValue(), **kw)


# ---------- Jerarquía multi-tenant ----------

class Empresa(Base):
    __tablename__ = "empresas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    nombre: Mapped[str] = mapped_column(String(150))
    rut: Mapped[str | None] = mapped_column(String(12))
    contacto_email: Mapped[str | None] = mapped_column(String(150))
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()

    clientes: Mapped[list["Cliente"]] = relationship(back_populates="empresa")


class Cliente(Base):
    __tablename__ = "clientes"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("empresas.id"))
    nombre: Mapped[str] = mapped_column(String(150))
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()

    empresa: Mapped[Empresa] = relationship(back_populates="clientes")
    sucursales: Mapped[list["Sucursal"]] = relationship(back_populates="cliente")


class Sucursal(Base):
    __tablename__ = "sucursales"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    cliente_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("clientes.id"))
    nombre: Mapped[str] = mapped_column(String(100))
    direccion: Mapped[str | None] = mapped_column(String(200))
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()

    cliente: Mapped[Cliente] = relationship(back_populates="sucursales")
    tableros: Mapped[list["Tablero"]] = relationship(back_populates="sucursal")


class Usuario(Base):
    """rol: 'vsc' (sin scope) | 'empresa' (empresa_id) | 'cliente' (cliente_id, nunca edita)."""
    __tablename__ = "usuarios"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    empresa_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("empresas.id"))
    cliente_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("clientes.id"))
    nombre_usuario: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    rol: Mapped[str] = mapped_column(String(20))
    puede_editar: Mapped[bool] = db_default()
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()


# ---------- Infraestructura eléctrica ----------

class Tablero(Base):
    __tablename__ = "tableros"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sucursales.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    ubicacion: Mapped[str | None] = mapped_column(String(200))
    amperaje_nominal: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()

    sucursal: Mapped[Sucursal] = relationship(back_populates="tableros")
    dispositivos: Mapped[list["Dispositivo"]] = relationship(back_populates="tablero")
    circuitos: Mapped[list["Circuito"]] = relationship(back_populates="tablero")


class Dispositivo(Base):
    """Un AcuRev físico. token_ingesta autentica el POST del equipo."""
    __tablename__ = "dispositivos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tablero_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tableros.id"))
    modelo: Mapped[str] = db_default(String(50))
    numero_serie: Mapped[str | None] = mapped_column(String(50))
    direccion_ip: Mapped[str | None] = mapped_column(String(45))
    fecha_instalacion: Mapped[date | None]
    ultima_comunicacion: Mapped[datetime | None]
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()
    token_ingesta: Mapped[str | None] = mapped_column(String(64), unique=True)

    tablero: Mapped[Tablero] = relationship(back_populates="dispositivos")
    circuitos: Mapped[list["Circuito"]] = relationship(back_populates="dispositivo")


class CalibreCable(Base):
    """Opcional/futura. Existe pero está vacía."""
    __tablename__ = "calibres_cable"
    calibre_mm2: Mapped[Decimal] = mapped_column(Numeric(5, 2), primary_key=True)
    corriente_maxima: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()


class Circuito(Base):
    """CORE. canal_acurev = identificador del circuito dentro del AcuRev (puente CSV -> circuito)."""
    __tablename__ = "circuitos"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tablero_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("tableros.id"))
    dispositivo_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("dispositivos.id"))
    codigo: Mapped[str] = mapped_column(String(20))
    nombre: Mapped[str] = mapped_column(String(100))
    calibre_cable_mm2: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), ForeignKey("calibres_cable.calibre_mm2")
    )
    corriente_automatico: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    activo: Mapped[bool] = db_default()
    created_at: Mapped[datetime] = db_default()
    canal_acurev: Mapped[str | None] = mapped_column(String(30))

    tablero: Mapped[Tablero] = relationship(back_populates="circuitos")
    dispositivo: Mapped[Dispositivo | None] = relationship(back_populates="circuitos")


# ---------- Datos operacionales ----------

class Medicion(Base):
    """Usar SIEMPRE medido_en (hora real del AcuRev) para lógica de negocio, no created_at."""
    __tablename__ = "mediciones"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dispositivo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dispositivos.id"))
    circuito_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("circuitos.id"))
    medido_en: Mapped[datetime]
    voltaje_a: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    voltaje_b: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    voltaje_c: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    corriente_a: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    corriente_b: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    corriente_c: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    potencia_activa: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    energia_kwh: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))
    created_at: Mapped[datetime] = db_default()
    temperatura_tablero: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))


class Alarma(Base):
    """circuito_id: lleno en umbral_*/fase_caida; NULL en dispositivo_offline/temperatura_alta."""
    __tablename__ = "alarmas"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    dispositivo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("dispositivos.id"))
    circuito_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("circuitos.id"))
    tipo: Mapped[str] = mapped_column(String(30))
    severidad: Mapped[str] = db_default(String(20))
    valor_medido: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    valor_umbral: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    mensaje: Mapped[str | None] = mapped_column(String(255))
    generado_en: Mapped[datetime] = db_default()
    resuelto: Mapped[bool] = db_default()
    resuelto_en: Mapped[datetime | None]
    resuelto_por: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuarios.id"))


class UmbralConfigurado(Base):
    """corriente/voltaje/potencia -> por circuito_id. temperatura -> por tablero_id."""
    __tablename__ = "umbrales_configurados"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    tablero_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("tableros.id"))
    circuito_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("circuitos.id"))
    tipo_variable: Mapped[str] = mapped_column(String(30))
    valor_umbral: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    activo: Mapped[bool] = db_default()
    creado_por: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("usuarios.id"))
    created_at: Mapped[datetime] = db_default()
    updated_at: Mapped[datetime] = db_default()
