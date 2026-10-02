"""Formatos de las respuestas de la API (lo que el backend devuelve en JSON).

Separan lo que se guarda en la BBDD de lo que se muestra: por ejemplo,
password_hash existe en la tabla pero NUNCA aparece en una respuesta.
"""
from pydantic import BaseModel, ConfigDict


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre_usuario: str
    rol: str
    empresa_id: int | None
    cliente_id: int | None
    puede_editar: bool


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut
