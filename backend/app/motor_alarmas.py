"""Motor de alarmas por umbral (Etapa 14 — Historia 005).

Cada vez que entran mediciones nuevas (servicio_mediciones), se comparan con los
umbrales ACTIVOS de su circuito:
- corriente: la fase más cargada supera el máximo           → alarma 'umbral_corriente'
- voltaje:   alguna fase baja del mínimo o sube del máximo  → alarma 'umbral_voltaje'
- potencia:  la potencia activa (W) supera el máximo        → alarma 'umbral_potencia'

Reglas:
- Una sola alarma abierta por circuito y tipo: si el problema sigue, no se repite.
- Se resuelve sola cuando el valor vuelve a la normalidad con un margen del 2 %
  (histéresis: evita que un valor que oscila justo en el límite abra y cierre alarmas sin parar).
  Ejemplo: umbral 16 A → abre sobre 16 A, se resuelve recién bajo 15,68 A.
- Si el umbral se desactiva, la alarma abierta se resuelve con la siguiente medición.
- Severidad: 'critica' si el valor pasa el límite en 10 % o más; si no, 'moderada'.
- Las mediciones se revisan en orden de tiempo: si en un mismo envío hay un pico
  y luego vuelve a lo normal, queda registrada la alarma y su resolución.
La temperatura del tablero (PT100, Historia 009) queda para el final.
"""
import logging
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Alarma, Circuito, UmbralConfigurado

MARGEN = Decimal("0.02")    # histéresis para resolver
CRITICO = Decimal("0.10")   # exceso desde el que la alarma es crítica
TIPO_ALARMA = {"corriente": "umbral_corriente", "voltaje": "umbral_voltaje", "potencia": "umbral_potencia"}
FASES = ("a", "b", "c")
log = logging.getLogger("electromap.auditoria")


def _txt(valor: Decimal) -> str:
    return f"{valor:.1f}".replace(".", ",")


def _fases(fila: dict, variable: str) -> list[tuple[str, Decimal]]:
    return [(f.upper(), Decimal(str(fila[f"{variable}_{f}"]))) for f in FASES if fila.get(f"{variable}_{f}") is not None]


def _revisar(umbral: UmbralConfigurado, fila: dict):
    """Devuelve (fuera_de_rango, dentro_con_margen, detalle) o None si no hay datos de esa variable.

    detalle = (valor, limite, mensaje) cuando está fuera de rango.
    """
    maximo, minimo = umbral.valor_umbral, umbral.valor_minimo
    if umbral.tipo_variable == "potencia":
        if fila.get("potencia_activa") is None:
            return None
        valor = Decimal(str(fila["potencia_activa"]))
        if valor > maximo:
            return True, False, (valor, maximo, f"Potencia {_txt(valor / 1000)} kW supera el umbral de {_txt(maximo / 1000)} kW")
        return False, valor <= maximo * (1 - MARGEN), None

    fases = _fases(fila, umbral.tipo_variable)
    if not fases:
        return None
    if umbral.tipo_variable == "corriente":
        fase, valor = max(fases, key=lambda f: f[1])
        if valor > maximo:
            return True, False, (valor, maximo, f"Corriente {_txt(valor)} A en fase {fase} supera el umbral de {_txt(maximo)} A")
        return False, valor <= maximo * (1 - MARGEN), None

    # Voltaje: se busca la fase más alejada de su rango, hacia arriba o hacia abajo.
    peor = None
    for fase, valor in fases:
        if valor > maximo:
            exceso = (valor - maximo) / maximo
            detalle = (valor, maximo, f"Voltaje {_txt(valor)} V en fase {fase} supera el máximo de {_txt(maximo)} V")
        elif minimo is not None and valor < minimo:
            exceso = (minimo - valor) / minimo
            detalle = (valor, minimo, f"Voltaje {_txt(valor)} V en fase {fase} bajo el mínimo de {_txt(minimo)} V")
        else:
            continue
        if peor is None or exceso > peor[0]:
            peor = (exceso, detalle)
    if peor:
        return True, False, peor[1]
    dentro = all(v <= maximo * (1 - MARGEN) and (minimo is None or v >= minimo * (1 + MARGEN)) for _, v in fases)
    return False, dentro, None


def _severidad(valor: Decimal, limite: Decimal) -> str:
    return "critica" if abs(valor - limite) >= limite * CRITICO else "moderada"


def evaluar_mediciones(db: Session, filas: list[dict]) -> list[tuple[int, Alarma, str]]:
    """Revisa las mediciones nuevas y crea o resuelve alarmas (sin commit).

    Devuelve los eventos (tablero_id, alarma, 'creada' | 'resuelta') para avisar en tiempo real.
    """
    if not filas:
        return []
    ids = {f["circuito_id"] for f in filas}
    tablero_de = dict(db.execute(select(Circuito.id, Circuito.tablero_id).where(Circuito.id.in_(ids))).all())
    umbrales = {}
    for u in db.scalars(select(UmbralConfigurado).where(
            UmbralConfigurado.circuito_id.in_(ids), UmbralConfigurado.activo.is_(True))):
        umbrales[(u.circuito_id, u.tipo_variable)] = u
    abiertas = {}
    for a in db.scalars(select(Alarma).where(
            Alarma.circuito_id.in_(ids), Alarma.resuelto.is_(False), Alarma.tipo.in_(TIPO_ALARMA.values()))):
        abiertas[(a.circuito_id, a.tipo)] = a

    eventos = []
    for fila in sorted(filas, key=lambda f: f["medido_en"]):
        cid = fila["circuito_id"]
        for variable, tipo in TIPO_ALARMA.items():
            umbral, abierta = umbrales.get((cid, variable)), abiertas.get((cid, tipo))
            if umbral is None:
                if abierta is not None:  # el umbral se desactivó
                    abierta.resuelto, abierta.resuelto_en = True, fila["medido_en"]
                    eventos.append((tablero_de[cid], abierta, "resuelta"))
                    del abiertas[(cid, tipo)]
                continue
            resultado = _revisar(umbral, fila)
            if resultado is None:
                continue
            fuera, dentro, detalle = resultado
            if fuera and abierta is None:
                valor, limite, mensaje = detalle
                alarma = Alarma(dispositivo_id=fila["dispositivo_id"], circuito_id=cid, tipo=tipo,
                                severidad=_severidad(valor, limite), valor_medido=valor, valor_umbral=limite,
                                mensaje=mensaje, generado_en=fila["medido_en"])
                db.add(alarma)
                db.flush()
                abiertas[(cid, tipo)] = alarma
                eventos.append((tablero_de[cid], alarma, "creada"))
                log.warning("ALARMA %s: circuito %s — %s", tipo, cid, mensaje)
            elif dentro and abierta is not None:
                abierta.resuelto, abierta.resuelto_en = True, fila["medido_en"]
                eventos.append((tablero_de[cid], abierta, "resuelta"))
                del abiertas[(cid, tipo)]
                log.info("ALARMA %s resuelta: circuito %s volvió a la normalidad", tipo, cid)
    return eventos
