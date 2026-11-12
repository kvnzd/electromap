# Imagen del backend de ElectroMap (FastAPI + uvicorn).
# Se construye desde la RAÍZ del repositorio (necesita backend/ y database/):
#     docker build -f backend/Dockerfile -t electromap-backend .
# La usan docker-compose.yml (local) y Railway (producción).
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Misma estructura que el repositorio: los scripts encuentran database/schema.sql.
WORKDIR /srv/electromap/backend

# 1) Dependencias primero: si solo cambia el código, Docker reutiliza esta capa.
COPY backend/requirements.txt .
RUN pip install -r requirements.txt

# 2) Código y schema (los secretos NO se copian: .dockerignore deja fuera .env).
COPY backend/app ./app
COPY backend/scripts ./scripts
COPY database/schema.sql /srv/electromap/database/schema.sql

# 3) Usuario sin privilegios; carpetas donde la app escribe (registros y envíos del AcuRev).
RUN useradd --create-home --uid 1000 electromap \
    && mkdir -p logs ingesta_recibida \
    && chown -R electromap:electromap /srv/electromap
USER electromap

EXPOSE 8000
# Un solo proceso (sin --workers): el vigilante, el simulador y el canal en vivo viven en memoria.
# PORT lo entrega Railway; en local se usa 8000. --proxy-headers: detrás del HTTPS de Railway.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
