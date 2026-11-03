"""Administración de circuitos: lo que mide cada canal del AcuRev.

canal_acurev es el "puente" entre el CSV del equipo y la base de datos:
cuando el AcuRev envía datos del canal "C1", el sistema busca el circuito
con canal_acurev = "C1" dentro de ese mismo equipo.
"""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.autorizacion import (
    circuitos_visibles,
    dispositivos_visibles,
    obtener_en_scope,
    registrar_auditoria,
    requiere_editor,
    tableros_visibles,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import CalibreCable, Circuito, Dispositivo, Tablero, Usuario
from app.schemas import CircuitoCrear, CircuitoEditar, CircuitoOut
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/circuitos", tags=["administración: circuitos"])

_DUPLICADO = "Ya existe un circuito con ese código en el tablero, o ese canal ya está usado en el equipo"


def _validar_conexion(
    db: Session,
    usuario: Usuario,
    tablero_id: int,
    dispositivo_id: int | None,
    canal_acurev: str | None,
    calibre: Decimal | None,
) -> None:
    """Reglas de terreno: el equipo debe estar en el mismo tablero, el canal necesita
    un equipo y el calibre debe existir en la tabla de calibres."""
    if dispositivo_id is not None:
        equipo = obtener_en_scope(
            db, usuario, Dispositivo, dispositivo_id, dispositivos_visibles(usuario), "dispositivo"
        )
        if equipo.tablero_id != tablero_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El equipo no está instalado en el tablero de este circuito")
    if canal_acurev is not None and dispositivo_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Para indicar canal_acurev, el circuito debe tener un equipo asignado")
    if calibre is not None and db.get(CalibreCable, calibre) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"El calibre {calibre} mm² no está registrado en la tabla de calibres")


@router.get("", response_model=list[CircuitoOut])
def listar_circuitos(
    tablero_id: int | None = None,
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Circuitos de mi ámbito. Opcional: filtrar por un tablero (?tablero_id=)."""
    consulta = circuitos_visibles(usuario, incluir_inactivos)
    if tablero_id is not None:
        consulta = consulta.where(Circuito.tablero_id == tablero_id)
    return db.scalars(consulta.order_by(Circuito.id)).all()


@router.get("/{circuito_id}", response_model=CircuitoOut)
def ver_circuito(circuito_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    return obtener_en_scope(db, usuario, Circuito, circuito_id, circuitos_visibles(usuario, True), "circuito")


@router.post("", response_model=CircuitoOut, status_code=status.HTTP_201_CREATED)
def crear_circuito(datos: CircuitoCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    obtener_en_scope(db, usuario, Tablero, datos.tablero_id, tableros_visibles(usuario), "tablero")
    _validar_conexion(db, usuario, datos.tablero_id, datos.dispositivo_id, datos.canal_acurev, datos.calibre_cable_mm2)

    circuito = Circuito(**datos.model_dump())
    db.add(circuito)
    guardar(db, circuito, _DUPLICADO)
    registrar_auditoria(
        usuario,
        f"CREA circuito id={circuito.id} tablero_id={circuito.tablero_id} "
        f"dispositivo_id={circuito.dispositivo_id} canal={circuito.canal_acurev!r}",
    )
    return circuito


@router.patch("/{circuito_id}", response_model=CircuitoOut)
def editar_circuito(
    circuito_id: int,
    datos: CircuitoEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    circuito = obtener_en_scope(db, usuario, Circuito, circuito_id, circuitos_visibles(usuario, True), "circuito")
    cambios = datos.model_dump(exclude_unset=True)

    # Se validan los valores como quedarían DESPUÉS del cambio.
    _validar_conexion(
        db,
        usuario,
        circuito.tablero_id,
        cambios.get("dispositivo_id", circuito.dispositivo_id),
        cambios.get("canal_acurev", circuito.canal_acurev),
        cambios.get("calibre_cable_mm2", circuito.calibre_cable_mm2),
    )
    aplicar_cambios(circuito, datos)
    guardar(db, circuito, _DUPLICADO)
    registrar_auditoria(usuario, f"EDITA circuito id={circuito.id} cambios={sorted(cambios)}")
    return circuito