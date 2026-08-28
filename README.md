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

## Instrucciones de instalación local

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # completar variables de conexión a PostgreSQL
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env          # VITE_API_URL y VITE_WS_URL
npm run dev
```

La aplicación quedará disponible en `http://localhost:5173` (frontend) y `http://localhost:8000` (backend).

## Integrantes

| Nombre | Rol |
|---|---|
| Kevin Zapata | Desarrollador Full Stack / Jefe de Proyecto |

Proyecto de Título **individual** — Ingeniería en Informática, Duoc UC (PTY4614).

## Metodología

Desarrollo ágil organizado en épicas (dimensionadas con Planning Poker / escala Fibonacci) distribuidas en un cronograma de 20 semanas (carta Gantt). El detalle de la definición del proyecto, la visión, el PMV y las épicas está documentado en `/docs`.

## Estructura del repositorio

```
electromap/
├── frontend/          # React + Vite + Tailwind
├── backend/            # FastAPI + WebSocket
├── docs/
│   ├── ElectroMap_PMV_Epicas.docx
│   ├── ElectroMap_Carta_Gantt.xlsx
│   └── Presentacion_ElectroMap.pptx
└── README.md
```

## Estado del proyecto

En desarrollo — Fase 1 (Definición del Proyecto APT) en curso. Alcance cerrado hasta diciembre: aplicación web 100% funcional, monitoreo en tiempo real, sin app móvil y sin control remoto.
