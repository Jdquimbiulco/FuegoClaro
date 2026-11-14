# FuegoClaro

Base funcional para la armonización y exploración de detecciones de focos de calor **MODIS** y **VIIRS** en Ecuador, usando datos de [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/). Proyecto preparado para el reto *NASA Space Apps 2026 — Harmonization of MODIS and VIIRS Hot Spots*.

> **Aviso científico:** una detección de foco de calor **no** equivale a un incendio confirmado ni a superficie quemada. La ausencia de detecciones no implica ausencia de fuego. Los conteos MODIS y VIIRS no son directamente comparables como área ni gravedad.

## Qué incluye

- **Backend** (FastAPI + Pandas/NumPy + Shapely): ingesta desde NASA FIRMS, normalización canónica, validación, asignación de provincia/región natural, agregaciones, comparación de sensores, detección de anomalías (z-score + FDR) y hallazgos deterministas trazables.
- **Frontend** (React + Vite + TypeScript + Tailwind + Leaflet + Recharts): dashboard, mapa interactivo, calendario, comparador MODIS/VIIRS, radar de anomalías, centro de hallazgos y página de metodología/procedencia.
- **Datos y trazabilidad**: dataset procesado en CSV/JSON, manifiesto con procedencia/hashes/transformaciones/limitaciones y muestra offline. La MAP_KEY de FIRMS vive solo en el backend.

## Estructura

- `backend/` — API, dominio, servicios e ingesta.
- `frontend/` — aplicación web.
- `data/processed/` — `detections.csv` y `manifest.json` publicados.
- `data/samples/` — muestra auténtica para demostración offline.
- `data/regions/` — GeoJSON provincial (Natural Earth 1:10m).
- `scripts/` — `build_regions.py`, `ingest_firms.py`.
- `docs/` — especificación original, API, métodos y runbook.
- `tests/backend/` — pruebas de normalización, validación, agregación y anomalías.
- `docker-compose.yml` — pila reproducible backend + frontend.
- `backend/Dockerfile`, `frontend/Dockerfile`, `frontend/nginx.conf` — imágenes y proxy de la API.

## Requisitos

- **Opción local:** Python 3.11+ (probado con 3.14), Node.js 20+, npm.
- **Opción Docker:** Docker Engine 24+ (o Docker Desktop) y Docker Compose v2.24+.
- Clave NASA FIRMS (MAP_KEY). No se incluye ni se versiona; solo es necesaria para volver a descargar datos.

## Configuración

1. **Backend**
   ```bash
   cd backend
   python -m venv .venv
   .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
   cp .env.example .env
   # Edita .env y define FIRMS_MAP_KEY=...
   ```
2. **Frontend**
   ```bash
   cd frontend
   npm install
   cp .env.example .env  # opcional: VITE_API_BASE_URL=http://localhost:8000/api/v1
   ```

## Ejecución

- **API**: `cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000` (docs en `/docs`).
- **Web**: `cd frontend && npm run dev` (http://localhost:5173).
- **Pruebas backend**: `backend/.venv/bin/python -m pytest -q` (o `make test`)
- **Build frontend**: `cd frontend && npm run build` (o `make build`)

## Ejecución con Docker (recomendada para reproducibilidad)

La pila completa se levanta con Docker Compose: FastAPI en un contenedor, el build de Vite servido por Nginx en otro y el dataset montado como volumen persistente. No hace falta instalar Python ni Node en la máquina anfitriona.

**Requisitos:** Docker Engine 24+ (o Docker Desktop) y Docker Compose v2.24+.

```bash
# 1. Configura la clave FIRMS (opcional para solo consultar datos)
cp backend/.env.example backend/.env
# Edita backend/.env y define FIRMS_MAP_KEY=...

# 2. Construye y levanta la pila
docker compose up -d --build

# 3. Verifica
docker compose ps
curl http://localhost:8000/api/v1/health
```

- **Web:** <http://localhost:5173>
- **API:** <http://localhost:8000/api/v1> (docs en `/docs`)
- El frontend consume `/api/v1` a través del proxy interno de Nginx, así que no hay CORS ni URL de API hardcodeada.
- El volumen `./data:/app/data` conserva dataset, CSV crudos y manifiestos en el host.
- Si `data/processed/detections.csv` no existe, la app arranca en **modo muestra** con `data/samples/detections_sample.csv`.
- La clave FIRMS se inyecta en runtime desde `backend/.env`; `.dockerignore` la excluye de las imágenes.

Comandos útiles:

```bash
make docker-up       # docker compose up -d --build
make docker-down     # docker compose down
make docker-logs     # logs en vivo
make docker-test     # pytest dentro del contenedor (12 passed)
make docker-ingest   # descarga FIRMS y reinicia el backend

# Puertos alternativos si 8000/5173 están ocupados
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up -d --build
```

Guía detallada (arquitectura de imágenes, datos, puertos, troubleshooting y notas de producción): [`docs/06-docker.md`](docs/06-docker.md).

## Ingesta y actualización de datos

Genera/actualiza el dataset canónico desde NASA FIRMS (SP priorizado, NRT como complemento reciente, sin publicación parcial si falla):

```bash
backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw
```

- Respeta límites de la API (pausas y reintentos ante cuota/`Invalid MAP_KEY`).
- Escribe `data/processed/detections.csv`, `data/processed/manifest.json`, manifiesto histórico en `data/manifests/` y muestra en `data/samples/`.
- Para verificar integridad/cobertura: `backend/.venv/bin/python scripts/check_dataset.py`.
- Para regenerar geometrías provinciales: `backend/.venv/bin/python scripts/build_regions.py`.

## Datos, productos y cobertura

- Productos: `MODIS_SP`, `MODIS_NRT`, `VIIRS_NOAA20_SP`, `VIIRS_NOAA20_NRT` (producto documentado por registro).
- BBox Ecuador: `(-92.5, -5.5, -74.5, 2.0)`; puntos recortados a provincias (Natural Earth 1:10m).
- Hora local: UTC-5 continental, UTC-6 Galápagos.
- Confianza normalizada: MODIS 0–100 → baja <30, nominal 30–79, alta ≥80; VIIRS `l/n/h` → baja/nominal/alta (sin score numérico inventado).

## Limitaciones

- Detección ≠ incendio confirmado ≠ área quemada.
- Nubosidad, humo, ángulo y cobertura del sensor afectan los conteos.
- SP y NRT pueden diferir; anomalías dependen del histórico disponible.

## Atribución

Fuente: NASA FIRMS (MODIS Collection 6.1, VIIRS 375 m). Límites administrativos: Natural Earth 1:10m. Mapa base: CARTO/OpenStreetMap. No es un producto oficial de NASA.

## Documentación

- `GUIA_DE_INICIO.md` — guía completa paso a paso para entender y levantar el proyecto.
- `docs/PROMPT_MAESTRO.md` — especificación original del reto.
- `docs/01-overview.md` — arquitectura y flujo de datos.
- `docs/02-data-model.md` — campos canónicos, confianza y manifiesto.
- `docs/03-scientific-methods.md` — normalización, filtros, comparación y anomalías.
- `docs/04-api.md` — endpoints y parámetros.
- `docs/05-runbook.md` — operación, actualización y resolución de problemas.
- `docs/06-docker.md` — ejecución reproducible con Docker Compose.
