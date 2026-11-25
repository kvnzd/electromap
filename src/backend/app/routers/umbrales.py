"""Umbrales de alarma por circuito (Etapa 14 — Historia 005).

Cada circuito puede tener un umbral por variable:
- corriente (A) y potencia (W): solo máximo (valor_umbral).
- voltaje (V): mínimo (valor_minimo) y máximo (valor_umbral).
  Sugerido para 220 V fase-neutro (NTCSD, ±7,5 %): 203,5 a 236,5 V.
El motor de alarmas (app/motor_alarmas.py) los aplica a cada medición nueva.
Un umbral no se borra: se desactiva (activo = false) y se puede volver a activar.
"""
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autorizacion import (
    circuitos_visibles,
    obtener_en_scope,
    registrar_auditoria,
    requiere_editor,
    tableros_visibles,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Circuito, Tablero, UmbralConfigurado, Usuario
from app.schemas import UmbralCrear, UmbralEditar, UmbralOut
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/umbrales", tags=["alarmas: umbrales"])

_DUPLICADO = "Ese circuito ya tiene un umbral para esa variable (si está desactivado, edítalo y actívalo)"


def _validar_limites(tipo: str, maximo: Decimal, minimo: Decimal | None) -> None:
    if tipo == "voltaje":
        if minimo is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El umbral de voltaje necesita mínimo (valor_minimo) y máximo (valor_umbral)")
        if minimo >= maximo:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "El mínimo de voltaje debe ser menor que el máximo")
    elif minimo is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"El umbral de {tipo} solo tiene máximo: no indiques valor_minimo")


@router.get("", response_model=list[UmbralOut])
def listar_umbrales(tablero_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    """Umbrales (activos y desactivados) de los circuitos de un tablero."""
    obtener_en_scope(db, usuario, Tablero, tablero_id, tableros_visibles(usuario), "tablero")
    return db.scalars(
        select(UmbralConfigurado)
        .join(Circuito, UmbralConfigurado.circuito_id == Circuito.id)
        .where(Circuito.tablero_id == tablero_id)
        .order_by(UmbralConfigurado.circuito_id, UmbralConfigurado.tipo_variable)
    ).all()


@router.post("", response_model=UmbralOut, status_code=status.HTTP_201_CREATED)
def crear_umbral(datos: UmbralCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    obtener_en_scope(db, usuario, Circuito, datos.circuito_id, circuitos_visibles(usuario), "circuito")
    _validar_limites(datos.tipo_variable, datos.valor_umbral, datos.valor_minimo)

    umbral = UmbralConfigurado(**datos.model_dump(), creado_por=usuario.id)
    db.add(umbral)
    guardar(db, umbral, _DUPLICADO)
    registrar_auditoria(
        usuario,
        f"CREA umbral id={umbral.id} circuito_id={umbral.circuito_id} {umbral.tipo_variable} "
        f"min={umbral.valor_minimo} max={umbral.valor_umbral}",
    )
    return umbral


@router.patch("/{umbral_id}", response_model=UmbralOut)
def editar_umbral(
    umbral_id: int,
    datos: UmbralEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    umbral = db.get(UmbralConfigurado, umbral_id)
    if umbral is None or umbral.circuito_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "umbral no encontrado")
    obtener_en_scope(db, usuario, Circuito, umbral.circuito_id, circuitos_visibles(usuario, True), "circuito")
    cambios = datos.model_dump(exclude_unset=True)

    # Se validan los límites como quedarían DESPUÉS del cambio.
    _validar_limites(
        umbral.tipo_variable,
        cambios.get("valor_umbral", umbral.valor_umbral),
        cambios.get("valor_minimo", umbral.valor_minimo),
    )
    aplicar_cambios(umbral, datos)
    umbral.updated_at = datetime.now(timezone.utc)
    guardar(db, umbral, _DUPLICADO)
    registrar_auditoria(usuario, f"EDITA umbral id={umbral.id} cambios={sorted(cambios)}")
    return umbral
