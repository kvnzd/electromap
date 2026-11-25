"""Carga datos de DEMOSTRACIÓN en una base nueva (Etapa 22).

Pensado para `docker compose`: quien levante ElectroMap desde cero (por ejemplo el profesor)
ve de inmediato un tablero funcionando, con historial y datos en vivo.

Crea, si no existen:
- La tabla de calibres (ampacidades NCh Elec 4/2003, Tabla 8.7, grupo 1).
- Empresa → cliente → sucursal → tablero DEMO-01 con su equipo "Simulador" (SIM-001).
- 3 circuitos: C1 Alumbrado (16 A, 2,5 mm²), C2 Enchufes (20 A, 2,5 mm²), C3-TRI Motor trifásico (32 A, 6 mm²).
- Umbrales de ejemplo (corriente = automático; voltaje 203,5–236,5 V en C1).
- 1 día de mediciones simuladas (una cada 5 minutos) para que el Historial tenga datos.

Uso (en Docker):  docker compose exec backend python -m scripts.datos_demo
Uso (sin Docker): python -m scripts.datos_demo   (desde backend/, con el entorno virtual)

Protección: si la base YA tiene empresas y no tiene DEMO-01 (por ejemplo la base real),
no hace nada, salvo que se agregue --forzar. Si DEMO-01 ya existe, solo informa su número.
"""
import argparse
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db import SessionLocal
from app.models import (CalibreCable, Circuito, Cliente, Dispositivo, Empresa, Sucursal, Tablero,
                        UmbralConfigurado)
from scripts.simular_mediciones import simular

CODIGO = "DEMO-01"
# calibre mm² → corriente máxima A (NCh Elec 4/2003, Tabla 8.7, grupo 1: cobre en ducto, 3 conductores, 30 °C)
CALIBRES = {"1.5": 15, "2.5": 20, "4": 25, "6": 33, "10": 45, "16": 61, "25": 83, "35": 103,
            "50": 132, "70": 164, "95": 197}
CIRCUITOS = [  # código, nombre, automático (A), calibre (mm²)
    ("C1", "Alumbrado", "16", "2.5"),
    ("C2", "Enchufes", "20", "2.5"),
    ("C3-TRI", "Motor trifásico", "32", "6"),
]


def cargar(db, forzar: bool = False) -> tuple[int, bool]:
    """Crea los datos de demostración. Devuelve (id del tablero DEMO-01, si se creó ahora)."""
    existente = db.scalar(select(Tablero).where(Tablero.codigo == CODIGO))
    if existente:
        return existente.id, False
    if db.scalar(select(func.count()).select_from(Empresa)) and not forzar:
        raise SystemExit("La base ya tiene empresas y no tiene DEMO-01: no se cargan datos de demostración "
                         "(¿es la base real?). Si de verdad quieres cargarlos, agrega --forzar.")

    db.execute(insert(CalibreCable).values(
        [{"calibre_mm2": Decimal(c), "corriente_maxima": Decimal(a)} for c, a in CALIBRES.items()]
    ).on_conflict_do_nothing(index_elements=["calibre_mm2"]))

    empresa = Empresa(nombre="Empresa Demostración")
    db.add(empresa); db.flush()
    cliente = Cliente(empresa_id=empresa.id, nombre="Cliente Demostración")
    db.add(cliente); db.flush()
    sucursal = Sucursal(cliente_id=cliente.id, nombre="Sucursal Demostración", direccion="Datos simulados")
    db.add(sucursal); db.flush()
    tablero = Tablero(sucursal_id=sucursal.id, codigo=CODIGO, nombre="Tablero de demostración (datos simulados)",
                      amperaje_nominal=Decimal("63"))
    db.add(tablero); db.flush()
    equipo = Dispositivo(tablero_id=tablero.id, modelo="Simulador", numero_serie="SIM-001")
    db.add(equipo); db.flush()

    for codigo, nombre, automatico, calibre in CIRCUITOS:
        circuito = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo=codigo, nombre=nombre,
                            corriente_automatico=Decimal(automatico), calibre_cable_mm2=Decimal(calibre))
        db.add(circuito); db.flush()
        db.add(UmbralConfigurado(circuito_id=circuito.id, tipo_variable="corriente", valor_umbral=Decimal(automatico)))
        if codigo == "C1":
            db.add(UmbralConfigurado(circuito_id=circuito.id, tipo_variable="voltaje",
                                     valor_minimo=Decimal("203.5"), valor_umbral=Decimal("236.5")))
    db.commit()
    simular(db, tablero.id, dias=1, cada_minutos=5)
    return tablero.id, True


def main() -> None:
    parser = argparse.ArgumentParser(description="Datos de demostración para una base nueva de ElectroMap")
    parser.add_argument("--forzar", action="store_true", help="cargar aunque la base ya tenga otras empresas")
    args = parser.parse_args()
    with SessionLocal() as db:
        tablero_id, creado = cargar(db, args.forzar)
    print(f"{'Datos de demostración cargados' if creado else 'Los datos de demostración ya existían'}: "
          f"tablero {CODIGO} = número {tablero_id}.")
    if tablero_id != 1:
        print(f"OJO: el simulador en vivo de docker-compose usa el tablero 1. "
              f"Agrega SIMULADOR_VIVO_TABLERO={tablero_id} al .env de la raíz y reinicia el backend.")
    print("Abre http://localhost:8080 → En vivo → DEMO-01.")


if __name__ == "__main__":
    main()