"""Lector del CSV del AcuRev (Etapa 12 — Historia 003).

Convierte un envío del AcuRev en filas de la tabla `mediciones`. Formato real,
confirmado con el primer envío del equipo (25-11-2026):

- POST multipart/form-data con los campos `action` ("upload"), `datasource`
  (Meter ID) y `file` (el CSV, text/csv). También se acepta el CSV solo (text/csv).
- CSV: separador coma, decimal punto, 1 fila de encabezado y 1 fila por minuto.
- `Time` en ISO 8601 con offset sin dos puntos (2026-11-25T22:40:00-0300) = inicio del minuto.
- Columnas por canal: I001_A (A), P001_kW (kW), EP001_IMP_kWh (kWh) ... hasta el canal 018.
  Voltaje por fase: Va_V, Vb_V, Vc_V. No trae temperatura.

Cómo se elige qué columnas leer: `circuitos.canal_acurev`.
- "001"          → circuito monofásico en el canal 1 (fase A).
- "002,003,004"  → circuito trifásico: un canal por fase, en orden A, B, C
                   (potencia y energía = suma de los tres). Provisorio hasta ver
                   el CSV trifásico real.
"1" y "001" son el mismo canal.

Unidades: la base guarda la potencia en W (el CSV la trae en kW → ×1000).
No se usan Vnavg_V ni Iavg_A: promedian las fases B y C aunque estén vacías.
"""
import csv
import io
from datetime import datetime
from email.parser import BytesParser
from email.policy import HTTP

COLUMNA_HORA = "Time"
_FASES = ("a", "b", "c")


class FormatoInvalido(ValueError):
    """El envío no tiene el formato esperado del AcuRev."""


# ---------- 1. Del envío HTTP al texto del CSV ----------

def extraer_csv(cuerpo: bytes, content_type: str) -> list[tuple[str | None, str]]:
    """Devuelve [(nombre_archivo, texto_csv)] del envío.

    multipart/form-data → cada parte con archivo (campo `file`); otro tipo → el cuerpo completo.
    """
    if not content_type.lower().startswith("multipart/"):
        return [(None, _a_texto(cuerpo))]
    mensaje = BytesParser(policy=HTTP).parsebytes(
        f"Content-Type: {content_type}\r\n\r\n".encode("latin-1") + cuerpo
    )
    if not mensaje.is_multipart():
        raise FormatoInvalido("multipart sin partes (falta el boundary o está mal formado)")
    archivos = [
        (parte.get_filename(), _a_texto(parte.get_payload(decode=True) or b""))
        for parte in mensaje.iter_parts()
        if parte.get_filename() or parte.get_param("name", header="content-disposition") == "file"
    ]
    if not archivos:
        raise FormatoInvalido("el envío multipart no trae ningún archivo")
    return archivos


def _a_texto(datos: bytes) -> str:
    # utf-8-sig quita la marca BOM si el equipo la agrega.
    return datos.decode("utf-8-sig", errors="replace")


# ---------- 2. Del texto del CSV a filas ----------

def leer_filas(texto: str) -> list[dict[str, str]]:
    """Filas del CSV como diccionarios {columna: valor}. Ignora líneas vacías."""
    lineas = [l for l in texto.splitlines() if l.strip()]
    if not lineas:
        return []
    lector = csv.DictReader(io.StringIO("\n".join(lineas)))
    if not lector.fieldnames or COLUMNA_HORA not in lector.fieldnames:
        raise FormatoInvalido(f"el CSV no tiene la columna '{COLUMNA_HORA}'")
    return list(lector)


def leer_hora(valor: str) -> datetime:
    """'2026-11-25T22:40:00-0300' (o con '-03:00') → datetime con zona horaria."""
    try:
        momento = datetime.strptime(valor.strip(), "%Y-%m-%dT%H:%M:%S%z")
    except (ValueError, AttributeError):
        raise FormatoInvalido(f"hora inválida: {valor!r}") from None
    return momento


def _numero(fila: dict, columna: str) -> float | None:
    valor = (fila.get(columna) or "").strip()
    if not valor:
        return None
    try:
        return float(valor)
    except ValueError:
        return None


# ---------- 3. De las filas a mediciones de cada circuito ----------

def canales(canal_acurev: str | None) -> list[str]:
    """'001' → ['001']; '2, 3, 4' → ['002', '003', '004']; inválido → []."""
    if not canal_acurev:
        return []
    partes = [p.strip() for p in canal_acurev.split(",")]
    if not all(p.isdigit() and 1 <= int(p) <= 18 for p in partes) or len(partes) > 3:
        return []
    return [f"{int(p):03d}" for p in partes]


def medicion_de_circuito(fila: dict, canales_circuito: list[str]) -> dict | None:
    """Valores de un circuito en una fila del CSV, o None si faltan sus columnas."""
    if not canales_circuito or f"I{canales_circuito[0]}_A" not in fila:
        return None
    datos: dict = {}
    potencias, energias = [], []
    for fase, canal in zip(_FASES, canales_circuito):
        datos[f"voltaje_{fase}"] = _numero(fila, f"V{fase}_V")
        datos[f"corriente_{fase}"] = _numero(fila, f"I{canal}_A")
        potencias.append(_numero(fila, f"P{canal}_kW"))
        energias.append(_numero(fila, f"EP{canal}_IMP_kWh"))
    datos["potencia_activa"] = None if None in potencias else round(sum(potencias) * 1000, 2)  # kW → W
    datos["energia_kwh"] = None if None in energias else round(sum(energias), 3)
    return datos


def mediciones_del_envio(filas: list[dict], equipo_id: int, circuitos) -> tuple[list[dict], list[str]]:
    """Filas para `registrar_mediciones` + avisos de lo que no se pudo leer.

    circuitos: objetos con .id y .canal_acurev (los circuitos activos de este equipo).
    """
    mediciones, avisos = [], []
    con_canal = []
    for c in circuitos:
        lista = canales(c.canal_acurev)
        if lista:
            con_canal.append((c, lista))
        else:
            avisos.append(f"circuito {c.id}: canal_acurev {c.canal_acurev!r} no válido (se espera '001' o '002,003,004')")
    if not con_canal:
        avisos.append("el equipo no tiene circuitos con canal_acurev: el envío se guardó pero no se leyó")
        return [], avisos

    for numero, fila in enumerate(filas, start=2):  # fila 1 = encabezado
        try:
            momento = leer_hora(fila.get(COLUMNA_HORA, ""))
        except FormatoInvalido as error:
            avisos.append(f"fila {numero}: {error}")
            continue
        for circuito, lista in con_canal:
            datos = medicion_de_circuito(fila, lista)
            if datos is None:
                avisos.append(f"fila {numero}: el CSV no trae la columna I{lista[0]}_A (circuito {circuito.id})")
                continue
            mediciones.append({"dispositivo_id": equipo_id, "circuito_id": circuito.id,
                               "medido_en": momento, "temperatura_tablero": None, **datos})
    return mediciones, avisos
