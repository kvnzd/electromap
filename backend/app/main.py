"""ElectroMap API - punto de entrada del backend.

Levantar (desde la carpeta backend/, con el entorno virtual activado):
    uvicorn app.main:app --reload
"""
from fastapi import FastAPI

from app.routers import health

# Crea la aplicación. title y version aparecen en la documentación automática (/docs).
app = FastAPI(
    title="ElectroMap API",
    description="Backend del sistema de monitoreo de tableros eléctricos.",
    version="0.1.0",
)

# Registra las rutas de cada módulo.
app.include_router(health.router)


@app.get("/")
def raiz():
    """Hola mundo: confirma que la API está funcionando."""
    return {"mensaje": "Hola mundo desde ElectroMap API"}
