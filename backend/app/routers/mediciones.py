"""Mediciones de un tablero: historial (Etapa 18) y estado actual para el dashboard (Etapa 17).

GET /mediciones/historial?tablero_id=4&desde=...&hasta=...
GET /mediciones/estado-actual?tablero_id=4   (última medición de cada circuito + equipos + alarmas abiertas)

- Solo tableros del ámbito del usuario (404 si no existe, 403 si es ajeno).
- Rango máximo: 31 días (400 si es mayor o si 'hasta' no es posterior a 'desde').
- Para que el gráfico no reciba miles de puntos, las mediciones se PROMEDIAN por
  intervalos cuyo tamaño depende del rango pedido (ver _intervalo_para).
- Si no hay mediciones en el rango, responde hay_datos = false (la pantalla lo avisa).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.autorizacion import circuitos_visibles, dispositivos_visibles, obtener_en_scope, tableros_visibles
from app.db import get_db
from app.deps import get_usuario_actual
from app.models import Alarma, Circuito, Dispositivo, Medicion, Tablero, Usuario
from app.schemas import (
    AlarmaAbierta, CircuitoEstado, CircuitoHistorial, EquipoEstado, EstadoTableroOut, HistorialOut, PuntoHistorial,
    ResumenCircuito, UltimaMedicion,
)

router = APIRouter(prefix="/mediciones", tags=["mediciones"])

RANGO_MAXIMO = timedelta(days=31)
# Referencia fija para alinear los intervalos (así un mismo rango siempre da los mismos puntos).
_ORIGEN = datetime(2000, 1, 1, tzinfo=timezone.utc)
_CAMPOS = ("voltaje_a", "voltaje_b", "voltaje_c", "corriente_a", "corriente_b", "corriente_c", "potencia_activa")


def _intervalo_para(rango: timedelta) -> timedelta:
    """Tamaño de cada punto: ≤6 h → 1 min · ≤2 días → 5 min · ≤7 días → 15 min · más → 1 h."""
    if rango <= timedelta(hours=6):
        return timedelta(minutes=1)
    if rango <= timedelta(days=2):
        return timedelta(minutes=5)
    if rango <= timedelta(days=7):
        return timedelta(minutes=15)
    return timedelta(hours=1)


def _a_utc(momento: datetime) -> datetime:
    """Una fecha sin zona horaria se interpreta como UTC."""
    return momento if momento.tzinfo else momento.replace(tzinfo=timezone.utc)


def _numero(valor) -> float | None:
    return None if valor is None else round(float(valor), 2)


@router.get("/historial", response_model=HistorialOut)
def historial(
    tablero_id: int,
    desde: datetime = Query(description="Inicio del rango (ISO 8601; sin zona = UTC)"),
    hasta: datetime = Query(description="Fin del rango (ISO 8601; sin zona = UTC)"),
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Mediciones de los circuitos de un tablero en un rango de fechas, promediadas por intervalos."""
    desde, hasta = _a_utc(desde), _a_utc(hasta)
    if hasta <= desde:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "'hasta' debe ser posterior a 'desde'")
    if hasta - desde > RANGO_MAXIMO:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El rango máximo es de 31 días")

    obtener_en_scope(db, usuario, Tablero, tablero_id, tableros_visibles(usuario, True), "tablero")
    circuitos = db.scalars(
        circuitos_visibles(usuario).where(Circuito.tablero_id == tablero_id).order_by(Circuito.codigo)
    ).all()

    intervalo = _intervalo_para(hasta - desde)
    en_rango = (Medicion.medido_en >= desde) & (Medicion.medido_en < hasta)
    ids = [c.id for c in circuitos]

    # 1) Puntos del gráfico: promedio de cada variable por circuito e intervalo (date_bin de PostgreSQL).
    bloque = func.date_bin(intervalo, Medicion.medido_en, _ORIGEN).label("momento")
    filas = db.execute(
        select(Medicion.circuito_id, bloque, *[func.avg(getattr(Medicion, c)).label(c) for c in _CAMPOS])
        .where(Medicion.circuito_id.in_(ids), en_rango)
        .group_by(Medicion.circuito_id, bloque)
        .order_by(Medicion.circuito_id, bloque)
    ).all() if ids else []
    puntos: dict[int, list[PuntoHistorial]] = {i: [] for i in ids}
    for fila in filas:
        puntos[fila.circuito_id].append(
            PuntoHistorial(t=fila.momento, **{c: _numero(getattr(fila, c)) for c in _CAMPOS})
        )

    # 2) Resumen por circuito: máximos del período y energía consumida (contador final − inicial).
    corriente_max = func.max(func.greatest(Medicion.corriente_a, Medicion.corriente_b, Medicion.corriente_c))
    resumen = {
        f.circuito_id: f for f in db.execute(
            select(
                Medicion.circuito_id,
                corriente_max.label("corriente_max"),
                func.max(Medicion.potencia_activa).label("potencia_max"),
                (func.max(Medicion.energia_kwh) - func.min(Medicion.energia_kwh)).label("energia_kwh"),
            ).where(Medicion.circuito_id.in_(ids), en_rango).group_by(Medicion.circuito_id)
        ).all()
    } if ids else {}

    return HistorialOut(
        tablero_id=tablero_id,
        desde=desde,
        hasta=hasta,
        intervalo_segundos=int(intervalo.total_seconds()),
        hay_datos=any(puntos.values()),
        circuitos=[
            CircuitoHistorial(
                id=c.id, codigo=c.codigo, nombre=c.nombre, puntos=puntos[c.id],
                resumen=ResumenCircuito(
                    corriente_max=_numero(getattr(resumen.get(c.id), "corriente_max", None)),
                    potencia_max=_numero(getattr(resumen.get(c.id), "potencia_max", None)),
                    energia_kwh=_numero(getattr(resumen.get(c.id), "energia_kwh", None)),
                ),
            )
            for c in circuitos
        ],
    )


@router.get("/estado-actual", response_model=EstadoTableroOut)
def estado_actual(
    tablero_id: int,
    usuario: Usuario = Depends(get_usuario_actual),
    db: Session = Depends(get_db),
):
    """Foto inicial del dashboard: última medición de cada circuito, equipos y alarmas abiertas.

    Después, el dashboard se mantiene al día con el WebSocket /ws/tableros/{id}.
    """
    tablero = obtener_en_scope(db, usuario, Tablero, tablero_id, tableros_visibles(usuario, True), "tablero")
    circuitos = db.scalars(
        circuitos_visibles(usuario).where(Circuito.tablero_id == tablero_id).order_by(Circuito.codigo)
    ).all()
    equipos = db.scalars(
        dispositivos_visibles(usuario).where(Dispositivo.tablero_id == tablero_id).order_by(Dispositivo.id)
    ).all()

    # Última medición de cada circuito: DISTINCT ON de PostgreSQL (una fila por circuito, la más reciente).
    ids = [c.id for c in circuitos]
    ultimas = {
        m.circuito_id: m for m in db.scalars(
            select(Medicion).where(Medicion.circuito_id.in_(ids))
            .order_by(Medicion.circuito_id, Medicion.medido_en.desc())
            .ext(distinct_on(Medicion.circuito_id))
        ).all()
    } if ids else {}

    alarmas = db.scalars(
        select(Alarma).where(Alarma.dispositivo_id.in_([e.id for e in equipos]), Alarma.resuelto.is_(False))
        .order_by(Alarma.generado_en.desc())
    ).all() if equipos else []

    def _ultima(m):
        if m is None:
            return None
        return UltimaMedicion(medido_en=m.medido_en, **{
            c: _numero(getattr(m, c)) for c in (*_CAMPOS, "energia_kwh")})

    return EstadoTableroOut(
        tablero_id=tablero.id, codigo=tablero.codigo, nombre=tablero.nombre,
        equipos=[EquipoEstado(id=e.id, modelo=e.modelo, numero_serie=e.numero_serie,
                              ultima_comunicacion=e.ultima_comunicacion) for e in equipos],
        circuitos=[CircuitoEstado(id=c.id, codigo=c.codigo, nombre=c.nombre, dispositivo_id=c.dispositivo_id,
                                  corriente_automatico=_numero(c.corriente_automatico), ultima=_ultima(ultimas.get(c.id)))
                   for c in circuitos],
        alarmas_abiertas=[AlarmaAbierta(id=a.id, tipo=a.tipo, severidad=a.severidad, dispositivo_id=a.dispositivo_id,
                                        circuito_id=a.circuito_id, mensaje=a.mensaje, generado_en=a.generado_en)
                          for a in alarmas],
    )
