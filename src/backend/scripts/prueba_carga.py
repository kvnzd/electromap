"""Prueba de carga de ElectroMap (Etapa 20 — Historia 008).

Simula varios tableros enviando datos AL MISMO TIEMPO y varios usuarios mirando el dashboard.
Corre SOLO contra la base de PRUEBAS (TEST_DATABASE_URL), nunca contra la real.

Qué hace, todo en paralelo durante --segundos:
1. Ingesta HTTP: cada equipo hace POST /ingesta una vez por segundo (como el AcuRev).
2. Mediciones: cada tablero guarda una medición por circuito por segundo con
   registrar_mediciones (el camino que usará el lector del CSV, Etapa 12), que incluye
   el motor de alarmas, la temperatura estimada y el aviso por WebSocket.
3. Dashboard: navegadores conectados por WebSocket (uno por tablero, hasta 10) y usuarios
   consultando estado actual, historial y alarmas.
Al final comprueba que NO se perdió ningún dato y escribe un informe en resultados_carga/.

Uso (desde backend/, con el entorno virtual activado):
    python -m scripts.prueba_carga                          (10 tableros × 3 circuitos × 30 s)
    python -m scripts.prueba_carga --tableros 20 --segundos 60
OJO: borra y recrea el schema de la base de PRUEBAS (igual que pytest). La real no se toca.
"""
import os
import tempfile

# Registros e ingesta van a carpetas temporales (antes de importar la app).
os.environ["LOGS_CARPETA"] = tempfile.mkdtemp(prefix="electromap-logs-carga-")

import argparse  # noqa: E402
import json  # noqa: E402
import logging  # noqa: E402
import random  # noqa: E402
import statistics  # noqa: E402
import threading  # noqa: E402
import time  # noqa: E402
import urllib.error  # noqa: E402
import urllib.parse  # noqa: E402
import urllib.request  # noqa: E402
from collections import Counter, defaultdict  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from decimal import Decimal  # noqa: E402
from pathlib import Path  # noqa: E402

from sqlalchemy import create_engine, func, select  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.config import a_url_sqlalchemy, settings  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
SCHEMA_SQL = RAIZ / "database" / "schema.sql"
CARPETA_INFORMES = Path(__file__).resolve().parents[1] / "resultados_carga"
CLAVE_USUARIO = "CargaElectroMap2026"


def _misma_base(url_a: str, url_b: str) -> bool:
    a, b = make_url(a_url_sqlalchemy(url_a)), make_url(a_url_sqlalchemy(url_b))
    return (a.host, a.port, a.database) == (b.host, b.port, b.database)


def resumen_latencias(valores_ms: list[float]) -> dict:
    """n, promedio, mediana (p50), p95 y máximo en milisegundos."""
    if not valores_ms:
        return {"n": 0, "prom": None, "p50": None, "p95": None, "max": None}
    orden = sorted(valores_ms)
    p95 = orden[min(len(orden) - 1, max(0, round(0.95 * len(orden)) - 1))]
    return {"n": len(orden), "prom": round(statistics.fmean(orden)), "p50": round(statistics.median(orden)),
            "p95": round(p95), "max": round(orden[-1])}


def medir_latencia_bd(engine, veces: int = 10) -> int:
    """Mediana en ms de un SELECT 1: el viaje de ida y vuelta hasta la base de datos."""
    tiempos = []
    with engine.connect() as conn:
        for _ in range(veces):
            t0 = time.perf_counter()
            conn.exec_driver_sql("SELECT 1")
            tiempos.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(tiempos))


class Registro:
    """Junta latencias y errores de todos los hilos."""

    def __init__(self):
        self._candado = threading.Lock()
        self.latencias = defaultdict(list)
        self.errores = Counter()
        self.atrasos = 0

    def anotar(self, operacion: str, ms: float, ok: bool = True, detalle: str = ""):
        with self._candado:
            self.latencias[operacion].append(ms)
            if not ok:
                self.errores[f"{operacion}: {detalle}"] += 1


def _http(metodo, url, cuerpo=None, cabeceras=None):
    pedido = urllib.request.Request(url, data=cuerpo, method=metodo, headers=cabeceras or {})
    inicio = time.perf_counter()
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            datos = r.read()
            return r.status, datos, (time.perf_counter() - inicio) * 1000
    except urllib.error.HTTPError as e:
        return e.code, e.read(), (time.perf_counter() - inicio) * 1000
    except Exception as e:  # conexión rechazada, tiempo agotado...
        return 0, str(e).encode(), (time.perf_counter() - inicio) * 1000


def preparar_datos(SessionLocal, n_tableros, n_circuitos):
    """Crea una empresa de prueba con sus tableros, equipos (con clave), circuitos y umbrales."""
    from app.models import (CalibreCable, Circuito, Cliente, Dispositivo, Empresa, Sucursal, Tablero,
                            UmbralConfigurado, Usuario)
    from app.security import generar_clave_ingesta, hashear_clave_ingesta, hashear_password

    with SessionLocal() as db:
        db.add(CalibreCable(calibre_mm2=Decimal("2.5"), corriente_maxima=Decimal("20")))
        empresa = Empresa(nombre="Carga SpA"); db.add(empresa); db.flush()
        cliente = Cliente(empresa_id=empresa.id, nombre="Cliente carga"); db.add(cliente); db.flush()
        sucursal = Sucursal(cliente_id=cliente.id, nombre="Sucursal carga"); db.add(sucursal); db.flush()
        db.add(Usuario(nombre_usuario="carga_vsc", password_hash=hashear_password(CLAVE_USUARIO), rol="vsc",
                       puede_editar=True))
        equipos = []
        for i in range(n_tableros):
            tablero = Tablero(sucursal_id=sucursal.id, codigo=f"CARGA-{i + 1:02d}", nombre=f"Tablero de carga {i + 1}")
            db.add(tablero); db.flush()
            clave = generar_clave_ingesta()
            equipo = Dispositivo(tablero_id=tablero.id, numero_serie=f"CARGA-{i + 1:02d}",
                                 token_ingesta=hashear_clave_ingesta(clave))
            db.add(equipo); db.flush()
            circuitos = []
            for c in range(n_circuitos):
                circuito = Circuito(tablero_id=tablero.id, dispositivo_id=equipo.id, codigo=f"C{c + 1}",
                                    nombre=f"Circuito {c + 1}", corriente_automatico=Decimal("20"),
                                    calibre_cable_mm2=Decimal("2.5"))
                db.add(circuito); db.flush()
                circuitos.append(circuito.id)
            # Umbral bajo en C1 para que el motor de alarmas trabaje (abre y cierra alarmas).
            db.add(UmbralConfigurado(circuito_id=circuitos[0], tipo_variable="corriente", valor_umbral=Decimal("12")))
            equipos.append({"tablero_id": tablero.id, "dispositivo_id": equipo.id, "clave": clave,
                            "circuitos": circuitos})
        db.commit()
    return equipos


def ejecutar(n_tableros=10, n_circuitos=3, segundos=30, lectores=5, puerto=8765):
    # --- Protecciones: solo la base de PRUEBAS ---
    if not settings.test_database_url:
        raise SystemExit("Falta TEST_DATABASE_URL en .env: la prueba de carga solo corre en la base de pruebas.")
    url_pruebas = settings.test_database_url.get_secret_value()
    if _misma_base(url_pruebas, settings.database_url.get_secret_value()):
        raise SystemExit("PELIGRO: TEST_DATABASE_URL apunta a la base REAL. Prueba cancelada.")

    # La app usará la base de pruebas, sin vigilante ni simulador, y guardará los envíos en una carpeta temporal.
    settings.database_url = settings.test_database_url
    settings.vigilante_activo = False
    settings.simulador_vivo_tablero = None
    settings.ingesta_carpeta = Path(tempfile.mkdtemp(prefix="electromap-ingesta-carga-"))

    import uvicorn
    from websockets.sync.client import connect

    from app.db import SessionLocal, engine
    from app.main import app
    from app.models import Alarma, Medicion
    from app.servicio_mediciones import registrar_mediciones
    from app.tiempo_real import canal

    for nombre in ("electromap.auditoria", "electromap.seguridad"):
        logging.getLogger(nombre).setLevel(logging.ERROR)  # sin ruido en la terminal

    print("1/5 Recreando el schema de la base de PRUEBAS…")
    with engine.begin() as conn:
        conn.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;")
        conn.exec_driver_sql(SCHEMA_SQL.read_text(encoding="utf-8"))
    latencia_bd = medir_latencia_bd(engine)
    print(f"    Latencia hasta la base de datos: {latencia_bd} ms por consulta (mediana de 10 SELECT 1)")
    print(f"2/5 Creando {n_tableros} tableros × {n_circuitos} circuitos…")
    equipos = preparar_datos(SessionLocal, n_tableros, n_circuitos)

    print(f"3/5 Levantando el backend en el puerto {puerto}…")
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning",
                                             access_log=False))
    hilo_servidor = threading.Thread(target=servidor.run, daemon=True)
    hilo_servidor.start()
    while not servidor.started:
        time.sleep(0.1)
    base = f"http://127.0.0.1:{puerto}"
    estado, datos, _ = _http("POST", f"{base}/auth/login", urllib.parse.urlencode(
        {"username": "carga_vsc", "password": CLAVE_USUARIO}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"})
    if estado != 200:
        raise SystemExit(f"No se pudo iniciar sesión en el backend de prueba (HTTP {estado}).")
    token = json.loads(datos)["access_token"]

    registro = Registro()
    detener = threading.Event()
    recibidos = defaultdict(Counter)  # tablero_id → eventos recibidos por tipo
    inicio_mediciones = datetime.now(timezone.utc).replace(microsecond=0)
    # Motor propio para los "equipos": cada hilo con su conexión, sin competir con el backend.
    motor_equipos = create_engine(a_url_sqlalchemy(url_pruebas), pool_size=n_tableros, max_overflow=0)

    def navegador(eq):
        try:
            with connect(f"ws://127.0.0.1:{puerto}/ws/tableros/{eq['tablero_id']}", open_timeout=15) as ws:
                ws.send(json.dumps({"token": token}))
                while True:
                    try:
                        evento = json.loads(ws.recv(timeout=0.5))
                        recibidos[eq["tablero_id"]][evento.get("tipo")] += 1
                    except TimeoutError:
                        if detener.is_set():
                            break
        except Exception as e:
            registro.anotar("WebSocket", 0, False, type(e).__name__)

    def equipo(eq, semilla):
        azar = random.Random(semilla)
        cabecera = {"Authorization": f"Bearer {eq['clave']}", "Content-Type": "text/plain"}
        with Session(motor_equipos) as db:
            for tick in range(segundos):
                objetivo = inicio + tick
                espera = objetivo - time.perf_counter()
                if espera > 0:
                    time.sleep(espera)
                else:
                    registro.atrasos += 1
                momento = inicio_mediciones + timedelta(seconds=tick)
                cuerpo = f"prueba de carga;{eq['dispositivo_id']};{momento.isoformat()}\n".encode()
                estado, _, ms = _http("POST", f"{base}/ingesta", cuerpo, cabecera)
                registro.anotar("POST /ingesta", ms, estado == 200, f"HTTP {estado}")
                filas = []
                for cid in eq["circuitos"]:
                    corriente = round(azar.uniform(6, 15), 2)
                    filas.append({"dispositivo_id": eq["dispositivo_id"], "circuito_id": cid, "medido_en": momento,
                                  "voltaje_a": round(azar.uniform(214, 226), 1), "corriente_a": corriente,
                                  "potencia_activa": round(220 * corriente * 0.92, 1), "energia_kwh": tick / 100})
                t0 = time.perf_counter()
                try:
                    registrar_mediciones(db, filas, notificar=canal.publicar_desde_hilo)
                    registro.anotar("Guardar mediciones", (time.perf_counter() - t0) * 1000)
                except Exception as e:
                    db.rollback()
                    registro.anotar("Guardar mediciones", (time.perf_counter() - t0) * 1000, False, type(e).__name__)

    def lector(semilla):
        azar = random.Random(semilla)
        cabecera = {"Authorization": f"Bearer {token}"}
        while not detener.is_set():
            eq = azar.choice(equipos)
            ahora = datetime.now(timezone.utc)
            consultas = [
                ("GET estado-actual", f"/mediciones/estado-actual?tablero_id={eq['tablero_id']}"),
                ("GET historial 1 h", "/mediciones/historial?" + urllib.parse.urlencode({
                    "tablero_id": eq["tablero_id"], "desde": (ahora - timedelta(hours=1)).isoformat(),
                    "hasta": (ahora + timedelta(minutes=5)).isoformat()})),
                ("GET alarmas", f"/alarmas?tablero_id={eq['tablero_id']}&estado=todas"),
            ]
            for operacion, ruta in consultas:
                estado, _, ms = _http("GET", base + ruta, cabeceras=cabecera)
                registro.anotar(operacion, ms, estado == 200, f"HTTP {estado}")
            time.sleep(0.2)

    print(f"4/5 Carga en curso: {segundos} s, {n_tableros} equipos enviando, "
          f"{min(n_tableros, 10)} navegadores en vivo y {lectores} usuarios consultando…")
    navegadores = [threading.Thread(target=navegador, args=(eq,)) for eq in equipos[:10]]
    for h in navegadores:
        h.start()
    time.sleep(2)  # que los navegadores alcancen a conectarse
    inicio = time.perf_counter() + 1
    hilos_equipos = [threading.Thread(target=equipo, args=(eq, i)) for i, eq in enumerate(equipos)]
    hilos_lectores = [threading.Thread(target=lector, args=(100 + i,)) for i in range(lectores)]
    for h in hilos_equipos + hilos_lectores:
        h.start()
    for h in hilos_equipos:
        h.join()
    duracion = time.perf_counter() - inicio
    time.sleep(3)  # últimos avisos en camino
    detener.set()
    for h in hilos_lectores + navegadores:
        h.join()
    servidor.should_exit = True
    hilo_servidor.join(timeout=10)

    print("5/5 Verificando que no se perdió ningún dato…")
    esperadas = n_tableros * n_circuitos * segundos
    with SessionLocal() as db:
        guardadas = db.scalar(select(func.count()).select_from(Medicion))
        alarmas_creadas = db.scalar(select(func.count()).select_from(Alarma))
    archivos = sum(1 for a in settings.ingesta_carpeta.rglob("*_cuerpo.txt"))
    avisos_esperados = n_circuitos * segundos
    avisos = [recibidos[eq["tablero_id"]]["medicion"] for eq in equipos[:10]]

    resultado = {
        "parametros": {"tableros": n_tableros, "circuitos": n_circuitos, "segundos": segundos, "lectores": lectores},
        "duracion_s": round(duracion, 1),
        "latencia_bd_ms": latencia_bd,
        "mediciones": {"esperadas": esperadas, "guardadas": guardadas},
        "ingesta": {"esperados": n_tableros * segundos, "archivos": archivos},
        "websocket": {"navegadores": len(navegadores), "avisos_esperados_c_u": avisos_esperados,
                      "avisos_min": min(avisos) if avisos else 0, "avisos_max": max(avisos) if avisos else 0},
        "alarmas_creadas": alarmas_creadas,
        "latencias": {op: resumen_latencias(v) for op, v in registro.latencias.items()},
        "errores": dict(registro.errores),
        "atrasos": registro.atrasos,
    }
    resultado["sin_perdida"] = (guardadas == esperadas and archivos == n_tableros * segundos
                                and all(a == avisos_esperados for a in avisos))
    resultado["sin_errores"] = not registro.errores
    return resultado


def informe(r: dict) -> str:
    p = r["parametros"]
    filas = "\n".join(
        f"| {op} | {s['n']} | {s['prom']} | {s['p50']} | {s['p95']} | {s['max']} |"
        for op, s in sorted(r["latencias"].items()))
    errores = "\n".join(f"- {k}: {v}" for k, v in r["errores"].items()) or "- Ninguno."
    ok = lambda b: "✅ Sí" if b else "❌ No"  # noqa: E731
    m, i, w = r["mediciones"], r["ingesta"], r["websocket"]
    if r["latencia_bd_ms"] >= 50:
        lectura = (f"La base de datos está a {r['latencia_bd_ms']} ms por consulta y cada operación hace varias "
                   "consultas seguidas: los tiempos de respuesta y los ciclos atrasados se explican principalmente "
                   "por esa distancia (backend en el PC local, base en Railway), no por el código. En producción "
                   "el backend y la base quedan en la misma red de Railway (Etapa 21) y la prueba se repite ahí.")
    else:
        lectura = (f"El backend y la base de datos están cerca ({r['latencia_bd_ms']} ms por consulta): "
                   "los tiempos reflejan el rendimiento del sistema.")
    return f"""# Prueba de carga ElectroMap — {datetime.now().strftime('%Y-%m-%d %H:%M')}

Etapa 20 — Historia 008. Generado por `python -m scripts.prueba_carga`.

## Escenario

- **{p['tableros']} tableros** con **{p['circuitos']} circuitos** cada uno, enviando **1 vez por segundo** durante **{p['segundos']} s** ({p['tableros'] * p['circuitos']} mediciones por segundo en total).
- Cada equipo hace además un `POST /ingesta` por segundo (como el AcuRev).
- **{w['navegadores']} navegadores** conectados por WebSocket y **{p['lectores']} usuarios** consultando estado actual, historial y alarmas sin pausa.
- Umbral de corriente bajo (12 A) en el C1 de cada tablero, para que el motor de alarmas trabaje durante la prueba.
- Backend (uvicorn, un proceso) y base de datos de **pruebas** en Railway: las latencias incluyen el viaje de red entre ambos (medido en la línea siguiente).
- Latencia de red hasta la base de datos: **{r['latencia_bd_ms']} ms** por consulta (mediana de 10 `SELECT 1`).
- Duración real de la carga: {r['duracion_s']} s. Ciclos atrasados (un equipo no alcanzó su segundo): {r['atrasos']}.

## Resultado

| Comprobación | Esperado | Obtenido | ¿OK? |
|---|---|---|---|
| Mediciones guardadas | {m['esperadas']} | {m['guardadas']} | {ok(m['guardadas'] == m['esperadas'])} |
| Envíos de ingesta guardados | {i['esperados']} | {i['archivos']} | {ok(i['archivos'] == i['esperados'])} |
| Avisos en vivo por navegador | {w['avisos_esperados_c_u']} | {w['avisos_min']}–{w['avisos_max']} | {ok(w['avisos_min'] == w['avisos_max'] == w['avisos_esperados_c_u'])} |
| Errores HTTP / excepciones | 0 | {sum(r['errores'].values())} | {ok(r['sin_errores'])} |

**Sin pérdida de datos: {ok(r['sin_perdida'])} · Sin errores: {ok(r['sin_errores'])}** · Alarmas creadas por el motor: {r['alarmas_creadas']}.

## Tiempos de respuesta (milisegundos)

| Operación | n | Promedio | Mediana (p50) | p95 | Máximo |
|---|---|---|---|---|---|
{filas}

## Lectura de los resultados

- {lectura}
- La prueba exige 1 envío por segundo por equipo, un ritmo más exigente que el intervalo de envío
  configurado en el AcuRev (a confirmar en las pruebas físicas).

## Errores

{errores}
"""


def main():
    parser = argparse.ArgumentParser(description="Prueba de carga de ElectroMap (solo base de PRUEBAS).")
    parser.add_argument("--tableros", type=int, default=10)
    parser.add_argument("--circuitos", type=int, default=3)
    parser.add_argument("--segundos", type=int, default=30)
    parser.add_argument("--lectores", type=int, default=5)
    parser.add_argument("--puerto", type=int, default=8765)
    a = parser.parse_args()
    r = ejecutar(a.tableros, a.circuitos, a.segundos, a.lectores, a.puerto)
    texto = informe(r)
    CARPETA_INFORMES.mkdir(exist_ok=True)
    archivo = CARPETA_INFORMES / f"carga_{datetime.now().strftime('%Y%m%d_%H%M')}_{a.tableros}x{a.circuitos}x{a.segundos}s.md"
    archivo.write_text(texto, encoding="utf-8")
    print(texto)
    print(f"Informe guardado en {archivo}")
    raise SystemExit(0 if r["sin_perdida"] and r["sin_errores"] else 1)


if __name__ == "__main__":
    main()
