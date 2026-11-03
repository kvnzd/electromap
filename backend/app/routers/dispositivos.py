"""Administración de dispositivos (analizadores AcuRev) y de su clave de ingesta.

La clave de ingesta es la "llave" con la que el equipo se identifica al enviar datos.
- Se genera al registrar el equipo y se muestra UNA sola vez.
- En la base de datos solo se guarda su hash (SHA-256), nunca la clave.
- Si se filtra o se cambia el equipo, se regenera y la anterior deja de servir.
"""
from fastapi import APIRouter, Depends, status
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
from app.models import Dispositivo, Tablero, Usuario
from app.schemas import DispositivoConClave, DispositivoCrear, DispositivoEditar, DispositivoOut
from app.security import generar_clave_ingesta, hashear_clave_ingesta
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/dispositivos", tags=["administración: dispositivos"])


def _con_clave(dispositivo: Dispositivo, clave: str) -> DispositivoConClave:
    """Arma la respuesta que incluye la clave en texto (solo al crear o regenerar)."""
    datos = DispositivoOut.model_validate(dispositivo).model_dump()
    return DispositivoConClave(**datos, clave_ingesta=clave)


@router.get("", response_model=list[DispositivoOut])
def listar_dispositivos(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    return db.scalars(dispositivos_visibles(usuario, incluir_inactivos).order_by(Dispositivo.id)).all()


@router.get("/{dispositivo_id}", response_model=DispositivoOut)
def ver_dispositivo(dispositivo_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    return obtener_en_scope(
        db, usuario, Dispositivo, dispositivo_id, dispositivos_visibles(usuario, True), "dispositivo"
    )


@router.post("", response_model=DispositivoConClave, status_code=status.HTTP_201_CREATED)
def crear_dispositivo(datos: DispositivoCrear, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    """Registra un AcuRev en un tablero del ámbito del usuario y genera su clave."""
    obtener_en_scope(db, usuario, Tablero, datos.tablero_id, tableros_visibles(usuario), "tablero")

    clave = generar_clave_ingesta()
    dispositivo = Dispositivo(**datos.model_dump(), token_ingesta=hashear_clave_ingesta(clave))
    db.add(dispositivo)
    guardar(db, dispositivo)
    # En auditoría queda QUE se generó una clave, nunca la clave.
    registrar_auditoria(usuario, f"CREA dispositivo id={dispositivo.id} tablero_id={dispositivo.tablero_id} (clave generada)")
    return _con_clave(dispositivo, clave)


@router.patch("/{dispositivo_id}", response_model=DispositivoOut)
def editar_dispositivo(
    dispositivo_id: int,
    datos: DispositivoEditar,
    usuario: Usuario = Depends(requiere_editor),
    db: Session = Depends(get_db),
):
    dispositivo = obtener_en_scope(
        db, usuario, Dispositivo, dispositivo_id, dispositivos_visibles(usuario, True), "dispositivo"
    )
    cambios = aplicar_cambios(dispositivo, datos)
    guardar(db, dispositivo)
    registrar_auditoria(usuario, f"EDITA dispositivo id={dispositivo.id} cambios={sorted(cambios)}")
    return dispositivo


@router.post("/{dispositivo_id}/regenerar-clave", response_model=DispositivoConClave)
def regenerar_clave(dispositivo_id: int, usuario: Usuario = Depends(requiere_editor), db: Session = Depends(get_db)):
    """Genera una clave nueva. La anterior deja de funcionar de inmediato."""
    dispositivo = obtener_en_scope(
        db, usuario, Dispositivo, dispositivo_id, dispositivos_visibles(usuario, True), "dispositivo"
    )
    clave = generar_clave_ingesta()
    dispositivo.token_ingesta = hashear_clave_ingesta(clave)
    guardar(db, dispositivo)
    registrar_auditoria(usuario, f"REGENERA clave del dispositivo id={dispositivo.id}")
    return _con_clave(dispositivo, clave)