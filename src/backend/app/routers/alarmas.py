"""Alarmas de un tablero (Etapa 15 — Historia 005).

- GET /alarmas?tablero_id=&estado=abiertas|resueltas|todas : listado, la más reciente primero.
- PATCH /alarmas/{id}/resolver : cierre manual por una persona (queda registrado quién).
  Sirve para cerrar una alarma cuya causa ya se atendió. Si el problema sigue
  (sobrecorriente, equipo desconectado...), el sistema abrirá una alarma nueva.
Las alarmas no se crean ni se borran a mano: las crea el sistema (vigilante y motor de alarmas).
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.autorizacion import (
    dispositivos_visibles,
    obtener_en_scope,
    registrar_auditoria,
    requiere_editor,
    tableros_visibles,
)
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Alarma, Dispositivo, Tablero, Usuario
from app.schemas import AlarmaOut
from app.tiempo_real import canal, evento_alarma

router = APIRouter(prefix="/alarmas", tags=["alarmas"])


def _salida(alarma: Alarma, nombre_usuario: str | None) -> AlarmaOut:
    return AlarmaOut.model_validate(alarma).model_copy(update={"resuelto_por_nombre": nombre_usuario})


@router.get("", response_model=list[AlarmaOut])
def listar_alarmas(
    tablero_id: int,
    estado: Literal["abiertas", "resueltas", "todas"] = "abiertas",
    limite: int = Query(200, ge=1, le=500),
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Alarmas de los equipos de un tablero (también de equipos ya desactivados)."""
    obtener_en_scope(db, usuario, Tablero, tablero_id, tableros_visibles(usuario, True), "tablero")
    consulta = (
        select(Alarma, Usuario.nombre_usuario)
        .join(Dispositivo, Alarma.dispositivo_id == Dispositivo.id)
        .outerjoin(Usuario, Alarma.resuelto_por == Usuario.id)
        .where(Dispositivo.tablero_id == tablero_id)
    )
    if estado == "abiertas":
        consulta = consulta.where(Alarma.resuelto.is_(False))
    elif estado == "resueltas":
        consulta = consulta.where(Alarma.resuelto.is_(True))
    filas = db.execute(consulta.order_by(Alarma.generado_en.desc(), Alarma.id.desc()).limit(limite)).all()
    return [_salida(alarma, nombre) for alarma, nombre in filas]


@router.patch("/{alarma_id}/resolver", response_model=AlarmaOut)
def resolver_alarma(alarma_id: int, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    alarma = db.get(Alarma, alarma_id)
    if alarma is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alarma no encontrada")
    equipo = obtener_en_scope(db, usuario, Dispositivo, alarma.dispositivo_id,
                              dispositivos_visibles(usuario, True), "dispositivo")
    if alarma.resuelto:
        raise HTTPException(status.HTTP_409_CONFLICT, "La alarma ya está resuelta")

    alarma.resuelto, alarma.resuelto_en, alarma.resuelto_por = True, datetime.now(timezone.utc), usuario.id
    tablero_id = equipo.tablero_id
    db.commit()
    registrar_auditoria(usuario, f"RESUELVE alarma id={alarma.id} tipo={alarma.tipo} dispositivo_id={alarma.dispositivo_id}")
    canal.publicar_desde_hilo(tablero_id, evento_alarma(alarma, "resuelta"))
    return _salida(alarma, usuario.nombre_usuario)
