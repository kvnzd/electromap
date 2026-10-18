"""ElectroMap API - punto de entrada del backend.

Levantar (desde la carpeta backend/, con el entorno virtual activado):
    uvicorn app.main:app --reload
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.logs import configurar_logs
from app.routers import auth, clientes, empresas, health, sucursales, tableros, usuarios

configurar_logs()

# Crea la aplicación. title y version aparecen en la documentación automática (/docs).
app = FastAPI(
    title="ElectroMap API",
    description="Backend del sistema de monitoreo de tableros eléctricos.",
    version="0.4.0",
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
app.include_router(usuarios.router)


@app.get("/")
def raiz():
    """Hola mundo: confirma que la API está funcionando."""
    return {"mensaje": "Hola mundo desde ElectroMap API"}
