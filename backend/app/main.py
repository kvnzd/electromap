"""ElectroMap API - punto de entrada del backend.

Levantar (desde la carpeta backend/, con el entorno virtual activado):
    uvicorn app.main:app --reload
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logs import configurar_logs
from app.routers import (
    auth, circuitos, clientes, dispositivos, empresas, health, ingesta, mediciones, sucursales, tableros, tiempo_real,
    umbrales, usuarios,
)
from app.simulador_vivo import simular_en_vivo
from app.tiempo_real import canal
from app.vigilante import vigilar

configurar_logs()


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    """Al arrancar: prepara el canal en tiempo real e inicia las tareas de fondo. Al apagar: las detiene."""
    canal.iniciar(asyncio.get_running_loop())
    tareas = []
    if settings.vigilante_activo:
        tareas.append(asyncio.create_task(vigilar()))
    if settings.simulador_vivo_tablero:
        tareas.append(asyncio.create_task(simular_en_vivo()))
    yield
    for tarea in tareas:
        tarea.cancel()


# Crea la aplicación. title y version aparecen en la documentación automática (/docs).
app = FastAPI(
    title="ElectroMap API",
    description="Backend del sistema de monitoreo de tableros eléctricos.",
    version="0.4.0",
    lifespan=ciclo_de_vida,
)

# CORS: permite que el frontend (otra dirección/puerto) llame a la API desde el navegador.
# Solo se aceptan las direcciones listadas en CORS_ORIGENES; cualquier otra web es bloqueada.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origenes,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Authorization", "Content-Type"],
)

# Registra las rutas de cada módulo.
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(empresas.router)
app.include_router(clientes.router)
app.include_router(sucursales.router)
app.include_router(tableros.router)
app.include_router(dispositivos.router)
app.include_router(circuitos.router)
app.include_router(ingesta.router)
app.include_router(mediciones.router)
app.include_router(tiempo_real.router)
app.include_router(umbrales.router)
app.include_router(usuarios.router)



@app.get("/")
def raiz():
    """Hola mundo: confirma que la API está funcionando."""
    return {"mensaje": "Hola mundo desde ElectroMap API"}
