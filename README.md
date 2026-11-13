# ElectroMap

## Descripción

ElectroMap es un sistema de monitoreo eléctrico en tiempo real para tableros eléctricos, desarrollado como Proyecto de Título individual de Ingeniería en Informática (Duoc UC), con **HQD Ingeniería** como cliente y caso de uso real.

El sistema captura mediciones de voltaje, corriente, potencia y energía desde un analizador instalado en el tablero eléctrico, las almacena de forma centralizada y las muestra en vivo en un dashboard web. **Es un sistema exclusivamente de monitoreo**: no permite operar, cortar ni modificar el tablero de forma remota (no es un sistema de control ni SCADA).

La plataforma es multi-cliente (multi-tenant): pertenece a VSC como propietario, quien administra a empresas (por ejemplo HQD Ingeniería), cada empresa administra a sus propios clientes finales, y cada cliente final visualiza únicamente los tableros de sus propias sucursales.

## Tecnologías

**Frontend**
- React + Vite
- Tailwind CSS
- WebSocket (cliente) para datos en tiempo real

**Backend**
- FastAPI (Python)
- WebSocket (servidor) para retransmisión en vivo
- PostgreSQL (alojado en Railway, en la nube)

**Hardware**
- Transformador de corriente (CT) núcleo partido H040, 60A
- Analizador de redes AcuRev-2110-mV-WEB2 (AccuEnergy)
- Comunicación sensor → backend vía HTTP

## Arquitectura (flujo de datos)

```
Tablero eléctrico
   └── CT H040 60A + Analizador AcuRev-2110-mV-WEB2
          │  HTTP (mediciones periódicas: V, I, P, E)
          ▼
   Backend FastAPI
          │  valida y persiste
          ▼
   PostgreSQL (Railway)
          │  retransmite lo recién guardado
          ▼
   WebSocket
          │
          ▼
   Frontend React (dashboard en vivo)
```

Modelo de acceso multi-tenant:

- **VSC** (propietario de la plataforma): acceso total, ve todas las empresas, clientes y tableros.
- **Empresa** (ej. HQD Ingeniería): ve y monitorea los tableros de sus propios clientes; solo puede editar si VSC se lo autoriza explícitamente.
- **Cliente final** (ej. una sucursal): solo puede ver sus propios tableros/sucursales; nunca puede editar.

## Cómo levantar el sistema

### Opción A — Con Docker (recomendado: todo desde cero en un comando)

Requisito: [Docker Desktop](https://www.docker.com/products/docker-desktop/) con el motor encendido ("Engine running").

```bash
# 1. Variables: copiar la plantilla como .env en la RAÍZ y completar JWT_SECRET
cp .env.docker.example .env
#    (generar la clave con: python -c "import secrets; print(secrets.token_hex(32))")

# 2. Construir y levantar base de datos + backend + frontend
docker compose up --build

# 3. Solo la primera vez, en otra terminal: crear el administrador VSC y cargar la demostración
docker compose exec backend python -m scripts.crear_usuario
docker compose exec backend python -m scripts.datos_demo

# 4. Abrir http://localhost:8080, iniciar sesión y entrar a "En vivo" → DEMO-01
```

La demostración crea el tablero **DEMO-01** (3 circuitos con calibre de cable y umbrales) con 1 día de historial, y el simulador en vivo del backend le envía una medición cada 5 segundos. Todos sus datos son simulados. `datos_demo` no carga nada si la base ya tiene otras empresas (protección de la base real).

| Servicio | Dirección | Detalle |
|---|---|---|
| Frontend | http://localhost:8080 | React compilado, servido por nginx |
| Backend (API) | http://localhost:8000/docs | FastAPI + WebSocket (`ws://localhost:8000/ws/tableros/{id}`) |
| Base de datos | contenedor `db` (PostgreSQL 16) | Se crea vacía con `database/schema.sql` la primera vez |

- Detener: `Ctrl+C` o `docker compose down`. Empezar de cero (borra los datos locales de Docker): `docker compose down -v`.
- Archivos Docker: `backend/Dockerfile` (se construye desde la raíz), `frontend/Dockerfile` (compila con Node y sirve con nginx), `frontend/nginx.conf`, `docker-compose.yml`, `.dockerignore`, `.env.docker.example`.
- Los secretos nunca entran a las imágenes: `.dockerignore` deja fuera `backend/.env`.

### Opción B — Desarrollo sin Docker

**Backend** (Python 3.13):

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env             # completar DATABASE_URL, JWT_SECRET y TEST_DATABASE_URL
python -m scripts.crear_usuario  # solo la primera vez
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Frontend** (Node 22):

```bash
cd frontend
npm install
npm run dev                      # http://localhost:5173 (usa el backend en http://127.0.0.1:8000)
```

Para otra dirección de backend: variable `VITE_API_URL` (por ejemplo en `frontend/.env`).

### Variables de entorno del backend

| Variable | Obligatoria | Descripción |
|---|---|---|
| `DATABASE_URL` | Sí | Conexión a PostgreSQL (`postgresql://usuario:clave@host:puerto/base`) |
| `JWT_SECRET` | Sí | Clave para firmar las sesiones (mínimo 32 caracteres) |
| `JWT_EXPIRA_MINUTOS` | No | Duración de la sesión (por defecto 480) |
| `TEST_DATABASE_URL` | Solo pruebas | Base exclusiva para `pytest` y la prueba de carga; nunca la real |
| `CORS_ORIGENES` | No | Direcciones del frontend autorizadas, en JSON: `["https://..."]` |
| `SIMULADOR_VIVO_TABLERO` | No | Id de un tablero `DEMO` para generar datos simulados en vivo |
| `SIMULADOR_VIVO_SEGUNDOS` | No | Cada cuántos segundos envía el simulador (por defecto 60; Docker usa 5) |
| `PORT` | No | Puerto del backend en la imagen Docker (Railway lo entrega; por defecto 8000) |

### Producción (publicado en internet)

| Parte | Servicio | Dirección |
|---|---|---|
| Frontend | Vercel (carpeta `frontend`, `frontend/vercel.json`) | https://electromap-psi.vercel.app |
| Backend | Railway (imagen `backend/Dockerfile`, `railway.json`) | https://electromap-production.up.railway.app |
| Base de datos | PostgreSQL en Railway (red interna con el backend) | — |

- Se publica solo al hacer **merge a `main`**: Railway reconstruye el backend (cambios en `backend/` o `database/`) y Vercel el frontend. Cada pull request recibe una vista previa de Vercel para revisarla antes del merge.
- Variables en Railway: `DATABASE_URL`, `JWT_SECRET`, `CORS_ORIGENES` (dirección de Vercel), `SIMULADOR_VIVO_TABLERO`, `SIMULADOR_VIVO_SEGUNDOS`. En Vercel: `VITE_API_URL` (dirección de Railway).
- Los cambios de estructura de la base nunca son automáticos: se aplican aparte y con respaldo.

### Pruebas

```bash
cd backend
pytest -q                            # pruebas automáticas (usa TEST_DATABASE_URL)
python -m scripts.prueba_carga       # prueba de carga; informe en backend/resultados_carga/
cd ../frontend && npm run lint
```

## Integrantes

| Nombre | Rol |
|---|---|
| Kevin Zapata | Desarrollador Full Stack / Jefe de Proyecto |

Proyecto de Título **individual** — Ingeniería en Informática, Duoc UC (PTY4614).

## Metodología

Desarrollo ágil organizado en épicas (dimensionadas con Planning Poker / escala Fibonacci) distribuidas en un cronograma de 20 semanas (carta Gantt). El detalle de la definición del proyecto, la visión, el PMV y las épicas está documentado en las carpetas `Fase 1/` y `Fase 2/`.

## Estructura del repositorio

```
electromap/
├── backend/              # FastAPI: app/ (API, WebSocket, alarmas), scripts/, tests/, Dockerfile
├── frontend/             # React + Vite + Tailwind, Dockerfile, nginx.conf
├── database/schema.sql   # Estructura oficial de la base de datos
├── docker-compose.yml    # Sistema completo con Docker (db + backend + frontend)
├── Fase 1/               # Evidencias de la Fase 1
├── Fase 2/               # Evidencias de la Fase 2
└── README.md
```

## Estado del proyecto

En desarrollo — Fase 2 (Desarrollo del Proyecto APT). Plataforma funcionando con datos simulados (tablero DEMO): administración multi-tenant, tiempo real, historial, alarmas por umbral, temperatura estimada de conductores, pruebas automáticas y de carga, Docker y despliegue público (Railway + Vercel). Pendiente: lector del CSV real del AcuRev y pruebas con el tablero real. Alcance: aplicación web de monitoreo (sin app móvil y sin control remoto del tablero).