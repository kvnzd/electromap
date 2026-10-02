"""Administración de empresas. Crear y editar es exclusivo del administrador VSC."""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.autorizacion import empresas_visibles, obtener_en_scope, registrar_auditoria, requiere_vsc
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Empresa, Usuario
from app.schemas import EmpresaCrear, EmpresaEditar, EmpresaOut
from app.utils import aplicar_cambios, guardar

router = APIRouter(prefix="/empresas", tags=["administración: empresas"])


@router.get("", response_model=list[EmpresaOut])
def listar_empresas(
    incluir_inactivos: bool = False,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """VSC ve todas; un usuario empresa o cliente ve solo la suya."""
    return db.scalars(empresas_visibles(usuario, incluir_inactivos).order_by(Empresa.id)).all()


@router.get("/{empresa_id}", response_model=EmpresaOut)
def ver_empresa(empresa_id: int, usuario: Usuario = Depends(get_usuario_actual), db: Session = Depends(get_db)):
    return obtener_en_scope(db, usuario, Empresa, empresa_id, empresas_visibles(usuario, True), "empresa")


@router.post("", response_model=EmpresaOut, status_code=status.HTTP_201_CREATED)
def crear_empresa(datos: EmpresaCrear, usuario: Usuario = Depends(requiere_vsc), db: Session = Depends(get_db)):
    empresa = Empresa(**datos.model_dump())
    db.add(empresa)
    guardar(db, empresa)
    registrar_auditoria(usuario, f"CREA empresa id={empresa.id} nombre={empresa.nombre!r}")
    return empresa


@router.patch("/{empresa_id}", response_model=EmpresaOut)
def editar_empresa(
    empresa_id: int,
    datos: EmpresaEditar,
    usuario: Usuario = Depends(requiere_vsc),
    db: Session = Depends(get_db),
):
    """Editar datos o desactivar ({"activo": false}). Desactivar una empresa
    corta el acceso a todos sus usuarios y a los de sus clientes."""
    empresa = obtener_en_scope(db, usuario, Empresa, empresa_id, empresas_visibles(usuario, True), "empresa")
    cambios = aplicar_cambios(empresa, datos)
    guardar(db, empresa)
    registrar_auditoria(usuario, f"EDITA empresa id={empresa.id} cambios={sorted(cambios)}")
    return empresa
