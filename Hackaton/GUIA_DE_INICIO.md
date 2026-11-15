# Guía de inicio de FuegoClaro

Esta guía reúne todo lo necesario para entender, levantar, verificar y actualizar el proyecto **FuegoClaro**, una base funcional para la armonización y exploración de detecciones de focos de calor **MODIS** y **VIIRS** de NASA FIRMS en Ecuador.

> **Aviso científico:** una detección de foco de calor **no** equivale a un incendio confirmado ni a superficie quemada. La ausencia de detecciones no implica ausencia de fuego. Los conteos MODIS y VIIRS no son directamente comparables como área ni gravedad.

---

## 1. Qué se construyó

El proyecto quedó implementado de punta a punta:

- **Ingesta real de NASA FIRMS** con productos SP priorizados y NRT como complemento reciente.
- **Normalización canónica** de MODIS y VIIRS a un mismo esquema, conservando la confianza original y el producto de origen.
- **Validación y limpieza**: descarte contabilizado de coordenadas inválidas, fechas inválidas, campos faltantes y duplicados.
- **Recorte geográfico** a las 24 provincias de Ecuador con Natural Earth 1:10m.
- **Asignación de provincia, región natural y hora local** (UTC-5 continental, UTC-6 Galápagos).
- **API FastAPI** con estadísticas, series, calendario, comparación de sensores, anomalías y hallazgos.
- **Detección de anomalías** con z-score, p-valor bilateral y control FDR Benjamini-Hochberg.
- **Hallazgos deterministas**: textos construidos sobre cálculos reales, sin LLM para inventar cifras.
- **Frontend React + Vite + TypeScript + Tailwind** con dashboard, mapa Leaflet, calendario, comparador, radar de anomalías, centro de hallazgos y metodología.
- **Trazabilidad**: manifiesto con procedencia, hashes, cobertura, transformaciones y limitaciones.
- **Pruebas backend** y scripts de verificación de integridad.
- **Documentación** de arquitectura, modelo de datos, métodos, API y operación.

### Estado actual de los datos

| Elemento | Valor |
| --- | --- |
| Registros válidos publicados | **116.729** |
| Cobertura | **2022-01-01 → 2026-11-12** |
| MODIS | **20.382** (`MODIS_SP` + `MODIS_NRT`) |
| VIIRS | **96.347** (`VIIRS_NOAA20_SP` + `VIIRS_NOAA20_NRT`) |
| Registros fuera de Ecuador excluidos | 61.392 |
| Duplicados / coordenadas inválidas / fechas inválidas | 0 / 0 / 0 |
| Provincias | 24 |
| Regiones naturales | Costa, Sierra, Amazonía, Galápagos |
| Versión del dataset | `fuegoclaro-20261113T003529Z` |

Archivos principales:

- `data/processed/detections.csv` — dataset canónico completo (28,4 MB, no versionado).
- `data/processed/manifest.json` — procedencia, cobertura, conteos y limitaciones.
- `data/samples/detections_sample.csv` — muestra auténtica para demo offline (versionada).
- `data/regions/ecuador_provinces.geojson` — geometrías provinciales.

---

## 2. Requisitos

### Opción A — Ejecución local

- **Python 3.11+** (probado con Python 3.14.8).
- **Node.js 20+** y npm (probado con Node 26.13.1 y npm 11.20.0).
- **Clave MAP_KEY de NASA FIRMS** para volver a descargar datos.
  - Se obtiene gratis en: <https://firms.modaps.eosdis.nasa.gov/api/map_key/>
  - En esta máquina ya está configurada en `backend/.env`.
  - La clave **nunca** debe ir al frontend ni a archivos versionados.

### Opción B — Ejecución con Docker (recomendada para reproducibilidad)

- **Docker Engine 24+** o Docker Desktop.
- **Docker Compose v2.24+** (se usa `env_file` opcional).
- Puertos libres `8000` y `5173`, salvo que los cambies con `BACKEND_PORT` y `FRONTEND_PORT`.
- No hace falta instalar Python ni Node en la máquina: todo corre dentro de contenedores.

```bash
docker --version
docker compose version
```

---

## 3. Estructura del proyecto

```text
Hackaton/
├── backend/                 API FastAPI y lógica de dominio
│   ├── app/
│   │   ├── api/             endpoints REST
│   │   ├── core/            configuración y logging
│   │   ├── domain/          normalización, agregaciones, anomalías, insights
│   │   ├── services/        cliente FIRMS, ingesta y acceso a datos
│   │   └── utils/           fechas, geometría y serialización JSON
│   ├── .env                 clave FIRMS y CORS (NO versionar)
│   ├── .env.example         plantilla de configuración
│   ├── requirements.txt
│   └── requirements-dev.txt
├── frontend/                Aplicación React + Vite
│   ├── src/
│   │   ├── pages/           dashboard, mapa, calendario, comparador, etc.
│   │   ├── components/      layout, UI, gráficos y mapa Leaflet
│   │   ├── context/         filtros globales sincronizados con la URL
│   │   ├── hooks/           consultas a la API
│   │   └── services/        cliente HTTP
│   ├── public/              favicon e íconos
│   └── package.json
├── data/
│   ├── processed/           detections.csv + manifest.json
│   ├── samples/             muestra offline versionada
│   ├── raw/                 CSV crudos de FIRMS (opcional)
│   ├── regions/             GeoJSON provincial
│   └── manifests/           historial de manifiestos
├── scripts/
│   ├── ingest_firms.py      descarga y construye el dataset
│   ├── build_regions.py     regenera geometrías provinciales
│   └── check_dataset.py     verifica integridad y cobertura
├── docs/                    documentación detallada
├── tests/backend/           pruebas automatizadas
├── backend/Dockerfile       imagen del backend FastAPI
├── frontend/Dockerfile      build Vite + Nginx
├── frontend/nginx.conf      proxy /api y fallback SPA
├── docker-compose.yml       pila backend + frontend + volumen de datos
├── .dockerignore            excluye secretos, venv, node_modules y datos crudos
├── README.md
├── GUIA_DE_INICIO.md        este archivo
├── Makefile
└── pytest.ini
```

---

## 4. Configuración inicial

### 4.1 Backend

Si el entorno virtual **ya existe** (caso de esta máquina), salta al paso 4.3.

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

Crea el archivo de entorno:

```bash
cp .env.example .env
```

Edita `backend/.env` y define tu clave:

```dotenv
FIRMS_MAP_KEY=tu_clave_de_nasa_firms
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

> En esta máquina `backend/.env` ya contiene una clave válida. No la compartas ni la subas a Git.

### 4.2 Frontend

Si `node_modules` **ya existe**, salta al paso 4.3.

```bash
cd frontend
npm install
cp .env.example .env
```

El archivo `frontend/.env` es opcional. Por defecto la app apunta a:

```dotenv
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

### 4.3 Verificar que el dataset existe

Desde la raíz del proyecto:

```bash
ls -lh data/processed/detections.csv data/processed/manifest.json
```

Si no existen, tienes dos opciones:

1. **Descargar datos reales** (requiere clave FIRMS y varios minutos):
   ```bash
   backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw
   ```
2. **Usar la muestra incluida** para una demo offline: la app detecta `data/samples/detections_sample.csv` y arranca en **modo muestra**. La muestra es auténtica, pero no representa el dataset completo.

---

## 5. Levantar el proyecto paso a paso

Se necesitan **dos terminales**: una para el backend y otra para el frontend.

### Terminal 1 — Backend

Desde la raíz del proyecto:

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

Debes ver algo similar a:

```text
FuegoClaro API iniciada | modo=real | registros=116729 | dataset=fuegoclaro-20261113T003529Z
Uvicorn running on http://127.0.0.1:8000
```

- API: <http://127.0.0.1:8000>
- Documentación interactiva: <http://127.0.0.1:8000/docs>
- Health check: <http://127.0.0.1:8000/api/v1/health>

### Terminal 2 — Frontend

Desde la raíz del proyecto:

```bash
cd frontend
npm run dev
```

Debes ver:

```text
VITE ready
Local: http://localhost:5173/
```

Abre en el navegador: **<http://localhost:5173>**

### Alternativa con Makefile

Desde la raíz:

```bash
make backend     # terminal 1
make frontend    # terminal 2
```

### Detener los servicios

- Si están en primer plano: `Ctrl+C` en cada terminal.
- Si quedaron en segundo plano:

```bash
# Ver qué está usando los puertos
ss -ltnp | grep -E ':(8000|5173)'

# Detener por PID
kill <PID>
```

---

## 6. Levantar con Docker (reproducible en cualquier máquina)

Docker Compose levanta la pila completa: backend FastAPI, frontend compilado servido por Nginx y el dataset montado como volumen. Es la forma recomendada para demo, evaluación o despliegue en otra máquina.

### 6.1 Configurar la clave FIRMS

```bash
cd /ruta/al/proyecto
cp backend/.env.example backend/.env
```

Edita `backend/.env`:

```dotenv
FIRMS_MAP_KEY=tu_clave_de_nasa_firms
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

La clave es **opcional para consultar** datos existentes o la muestra; solo se necesita para **volver a descargar** desde NASA FIRMS. El archivo `.env` está en `.gitignore` y en `.dockerignore`, por lo que no se hornea en las imágenes.

### 6.2 Construir y levantar

```bash
docker compose up -d --build
```

| Servicio | URL |
| --- | --- |
| Aplicación web | <http://localhost:5173> |
| API directa | <http://localhost:8000/api/v1> |
| Documentación interactiva | <http://localhost:8000/docs> |
| Health check | <http://localhost:8000/api/v1/health> |

El frontend consume `http://localhost:5173/api/v1/...`; Nginx lo reenvía internamente a `http://backend:8000`. Así la web y la API comparten origen y no hay problemas de CORS.

```bash
docker compose ps          # estado y healthchecks
docker compose logs -f     # logs en vivo
docker compose down        # detener (conserva imágenes y datos)
```

### 6.3 Datos y persistencia

`docker-compose.yml` monta:

```yaml
volumes:
  - ./data:/app/data
```

Comportamiento al arrancar:

- Existe `data/processed/detections.csv` → **modo real** con el dataset completo.
- No existe, pero sí `data/samples/detections_sample.csv` (versionado) → **modo muestra**.
- No hay ninguno → **modo vacío**; la interfaz lo indica sin inventar cifras.

La imagen del backend también copia `data/` en el build, así que un `docker run` sin volumen funciona de forma autocontenida. En Compose, el bind mount tiene prioridad y los archivos quedan en el host.

Descargar datos reales dentro de Docker:

```bash
docker compose run --rm backend python scripts/ingest_firms.py \
  --start 2022-01-01 \
  --end 2026-11-12 \
  --keep-raw

docker compose restart backend   # recarga el CSV en memoria
```

Verificar integridad:

```bash
docker compose run --rm backend python scripts/check_dataset.py
```

### 6.4 Pruebas dentro de Docker

```bash
docker compose run --rm backend python -m pytest -q
```

Resultado esperado: `28 passed`.

### 6.5 Cambiar puertos

Si `8000` o `5173` están ocupados:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up -d --build
```

- Web: <http://localhost:5180>
- API: <http://localhost:8010/api/v1>
- Docs: <http://localhost:8010/docs>

El proxy interno sigue funcionando porque usa el nombre de servicio `backend` dentro de la red de Compose, no el puerto publicado.

### 6.6 Cómo están construidas las imágenes

```text
Navegador
   ├── http://localhost:5173/            → Nginx → dist/ (SPA)
   └── http://localhost:5173/api/v1/...  → Nginx → http://backend:8000
                                                        │
                                                        ▼
                                              FastAPI + Uvicorn
                                                        │
                                                        ▼
                                              /app/data (bind mount ./data)
```

- **Backend:** `python:3.12-slim`, instala `requirements.txt` + `requirements-dev.txt`, copia `backend/`, `scripts/`, `tests/`, `pytest.ini` y `data/`, y expone Uvicorn en `8000` con healthcheck.
- **Frontend:** etapa `node:22-alpine` con `npm ci` y `npm run build` (`VITE_API_BASE_URL=/api/v1`), luego `nginx:1.27-alpine` sirviendo `dist/`, con proxy `/api/`, fallback SPA y caché larga para assets.
- **Secretos:** `.dockerignore` excluye `.env`, `venv`, `node_modules`, `data/raw` y `data/manifests`.

### 6.7 Comandos Makefile

```bash
make docker-up       # docker compose up -d --build
make docker-down     # docker compose down
make docker-logs     # logs en vivo
make docker-test     # pytest dentro del contenedor
make docker-ingest   # ingesta FIRMS + restart del backend
make docker-build    # solo construir imágenes
```

Guía ampliada de Docker, troubleshooting y notas de producción: [`docs/06-docker.md`](docs/06-docker.md).

---

## 7. Verificar que todo funciona

### 7.1 Health check

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Debe devolver `status: "ok"`, `data_mode: "real"` y `rows: 116729`.

### 7.2 Smoke test de la API

```bash
curl http://127.0.0.1:8000/api/v1/meta
curl http://127.0.0.1:8000/api/v1/stats/summary
curl http://127.0.0.1:8000/api/v1/comparison
curl http://127.0.0.1:8000/api/v1/anomalies
curl http://127.0.0.1:8000/api/v1/insights
```

### 7.3 Integridad del dataset

```bash
backend/.venv/bin/python scripts/check_dataset.py
```

Resultado esperado: `Sin problemas de integridad detectados.`

### 7.4 Pruebas automatizadas

```bash
backend/.venv/bin/python -m pytest -q
```

Resultado esperado: `28 passed`.

### 7.5 Build de producción del frontend

```bash
cd frontend
npm run build
```

El build genera `frontend/dist/`. Es normal ver una advertencia por el tamaño del bundle (~985 kB); no impide la ejecución.

---

## 8. Qué muestra cada sección de la app

| Ruta | Sección | Contenido |
| --- | --- | --- |
| `/` | Dashboard | Indicadores del periodo, serie mensual, confianza, regiones, provincias y últimas detecciones. |
| `/mapa` | Mapa | Detecciones geolocalizadas con clustering, popups, contornos provinciales y exportación. |
| `/calendario` | Calendario | Conteo diario, intensidad relativa y desglose MODIS/VIIRS. |
| `/comparador` | Comparador | MODIS vs VIIRS: conteos, cobertura, confianza y razón de conteos. |
| `/anomalias` | Anomalías | Parámetros interactivos, z-score, q-valor FDR y evidencia por día. |
| `/hallazgos` | Hallazgos | Tarjetas deterministas con indicador, evidencia, método y límite. |
| `/metodologia` | Metodología | Fuentes, pipeline, confianza, estadística, API y comandos. |

Los filtros globales (periodo, región, sensor y calidad) se guardan en la URL, por lo que puedes compartir una vista específica copiando el enlace.

---

## 9. API principal

Base URL: `http://localhost:8000/api/v1`

| Método | Ruta | Descripción |
| --- | --- | --- |
| GET | `/health` | Estado del servicio y del dataset. |
| GET | `/meta` | Versión, modo, cobertura, sensores, regiones y provincias. |
| GET | `/regions` | Regiones naturales y provincias. |
| GET | `/regions/geojson` | Geometrías provinciales para el mapa. |
| GET | `/provenance` | Manifiesto, hashes, transformaciones y fuentes. |
| GET | `/detections` | Detecciones paginadas o GeoJSON. |
| GET | `/detections/{id}` | Detalle de una detección. |
| GET | `/stats/summary` | Indicadores del periodo filtrado. |
| GET | `/stats/timeseries` | Serie diaria, semanal o mensual. |
| GET | `/calendar` | Calendario mensual por día local. |
| GET | `/comparison` | Comparación MODIS vs VIIRS. |
| GET | `/anomalies` | Anomalías con z-score y FDR. |
| GET | `/insights` | Hallazgos deterministas. |
| GET | `/export/detections.csv` | Exportación CSV con los filtros activos. |

Filtros comunes:

```text
start_date=YYYY-MM-DD
end_date=YYYY-MM-DD
region_id=all|costa|sierra|amazonia|galapagos|<provincia>
sensor=all|MODIS|VIIRS
confidence=low|nominal|high|nominal,high
daynight=D|N
min_frp=<número>
```

La documentación interactiva completa está en <http://127.0.0.1:8000/docs>.

---

## 10. Actualizar o regenerar los datos

### Ingesta completa

```bash
backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw
```

Consideraciones:

- Requiere `FIRMS_MAP_KEY` válida en `backend/.env`.
- Descarga por bloques de 5 días, con pausas para respetar la cuota de FIRMS.
- Prioriza productos **SP** y usa **NRT** solo para el tramo reciente sin SP.
- Si FIRMS falla o rechaza la clave, el proceso **aborta y no publica un dataset parcial**.
- No ejecutes dos ingestas en paralelo.
- Al terminar escribe:
  - `data/processed/detections.csv`
  - `data/processed/manifest.json`
  - historial en `data/manifests/`
  - muestra en `data/samples/`

### Regenerar geometrías provinciales

```bash
backend/.venv/bin/python scripts/build_regions.py
```

### Verificar integridad después de una ingesta

```bash
backend/.venv/bin/python scripts/check_dataset.py
backend/.venv/bin/python -m pytest -q
```

### Modelo de riesgo de incendios (ML)

El modelo usa el histórico FIRMS como etiqueta y añade clima, DEM y NDVI.
Trabaja por celda de 0.1° × día y predice horizontes de 0 a 7 días.

```bash
# 1. Dataset (sin NDVI si no hay EARTHDATA_TOKEN)
backend/.venv/bin/python scripts/build_fire_risk_dataset.py \
  --start 2022-01-01 --end 2026-11-12

# Prueba rápida sin red
backend/.venv/bin/python scripts/build_fire_risk_dataset.py \
  --limit-cells 100 --skip-weather --skip-dem --skip-ndvi

# 2. Entrenamiento
backend/.venv/bin/python scripts/train_fire_risk_model.py

# 3. Predicción
backend/.venv/bin/python scripts/predict_fire_risk.py \
  --lat -4.4161 --lon -79.54454 --date 2026-11-20 --window-days 7
```

- El token de Earthdata se define en `backend/.env`; **nunca** se versiona.
- Salidas: `data/processed/ml/` (dataset, modelo, métricas y umbrales).
- Si NDVI falla, el dataset se genera con `ndvi_available=0` y advertencia.
- Los niveles Bajo/Medio/Alto/Extremo son percentiles de validación; la
  probabilidad absoluta también se devuelve.
- Metodología completa: [`docs/07-ml-risk.md`](docs/07-ml-risk.md).

---

## 11. Decisiones metodológicas importantes

- **Productos:** `MODIS_SP`, `MODIS_NRT`, `VIIRS_NOAA20_SP` y `VIIRS_NOAA20_NRT`. El producto queda documentado por registro.
- **BBox de Ecuador:** `(-92.5, -5.5, -74.5, 2.0)`.
- **Recorte territorial:** contención geométrica contra provincias Natural Earth 1:10m; no se usan centroides ni cercanía.
- **Confianza MODIS:** score 0–100 conservado; baja <30, nominal 30–79, alta ≥80.
- **Confianza VIIRS:** `l/n/h` → baja/nominal/alta; **no** se inventa un score numérico.
- **Hora local:** UTC-5 continental y UTC-6 Galápagos; se usa para calendario y series diarias.
- **Anomalías:** conteo diario por región y sensor; línea base de la misma fecha ±7 días en años anteriores; z-score; p-valor normal bilateral; FDR Benjamini-Hochberg; mínimo 3 detecciones observadas y 10 días de línea base.
- **Hallazgos:** plantillas deterministas sobre agregaciones ya calculadas; sin LLM para cifras.
- **Deduplicación:** `id` determinista por producto, satélite, fecha, hora y coordenadas.

---

## 12. Limitaciones y uso responsable

- Detección de foco de calor ≠ incendio confirmado ≠ superficie quemada.
- La ausencia de detección no implica ausencia de fuego: nubes, humo, ángulo de observación y cobertura del sensor pueden ocultar píxeles.
- Un mismo frente de fuego puede generar varias detecciones y varios sensores pueden detectarlo de forma distinta.
- Los conteos MODIS y VIIRS no son intercambiables: difieren en resolución (~1 km vs ~375 m), sensibilidad, algoritmo y horario de pasada.
- La razón VIIRS/MODIS es una razón de **conteos**, no de área.
- Los productos SP y NRT pueden diferir; su procedencia se documenta por registro.
- Las anomalías describen conteos inusuales, no causas ni incendios confirmados.
- La línea base depende de la cobertura histórica disponible.
- Este proyecto es una herramienta de exploración y **no es un producto oficial de NASA**.

---

## 13. Seguridad de la clave FIRMS

- La clave vive únicamente en `backend/.env`.
- `.env` está en `.gitignore`; no se versiona.
- El frontend nunca recibe la clave: solo consume la API del backend.
- Si necesitas compartir el proyecto, comparte `backend/.env.example` (vacío), no el `.env` real.
- Si la clave se filtra, genera una nueva en NASA FIRMS y actualiza `backend/.env`.

Verificación rápida de que la clave no está en archivos versionados:

```bash
grep -rl "tu_clave" --exclude-dir=node_modules --exclude-dir=.venv --exclude-dir=data .
```

Solo debería aparecer `backend/.env`.

---

## 14. Solución de problemas

### El frontend dice “No se pudo conectar con el backend”

- Confirma que el backend está corriendo en el puerto 8000.
- Abre <http://127.0.0.1:8000/api/v1/health>.
- Verifica `frontend/.env` o el valor por defecto `VITE_API_BASE_URL`.
- Revisa que el origen esté permitido en `CORS_ORIGINS` (`http://localhost:5173` y `http://127.0.0.1:5173`).

### La app muestra “Modo muestra” o “No hay datos cargados”

- `data/processed/detections.csv` no existe o no es válido.
- Ejecuta la ingesta real o copia el dataset procesado.
- La muestra versionada hace que la app funcione en modo muestra, no con el dataset completo.

### La ingesta falla con `Invalid MAP_KEY` o error de cuota

- La API de FIRMS rechaza la clave por exceso de transacciones o clave inválida.
- Espera unos minutos y reintenta; no ejecutes ingestas paralelas.
- Verifica la clave en `backend/.env`.
- El dataset anterior permanece intacto: la ingesta no publica parciales.

### VIIRS o MODIS no cubren todo el periodo

- Es cobertura real de los productos, no un error de la interfaz.
- Consulta `date_by_sensor` en `/api/v1/meta` y `sources` en el manifiesto.
- En el dataset actual, `VIIRS_NOAA20_SP` llega hasta `2026-07-31` y `VIIRS_NOAA20_NRT` cubre desde `2026-08-01`.

### El mapa no muestra el contorno provincial

- Verifica que exista `data/regions/ecuador_provinces.geojson`.
- Regenera con `backend/.venv/bin/python scripts/build_regions.py`.
- Las detecciones siguen visibles aunque falle el contorno.

### Error de Python o dependencias

```bash
cd backend
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

### Error de Node o dependencias

```bash
cd frontend
rm -rf node_modules package-lock.json
npm install
```

### El puerto ya está ocupado

```bash
ss -ltnp | grep -E ':(8000|5173)'
kill <PID>
```

O usa otros puertos:

```bash
# Backend
.venv/bin/uvicorn app.main:app --reload --port 8001

# Frontend
npm run dev -- --port 5174
```

Si cambias el puerto del backend, actualiza `VITE_API_BASE_URL`.

### Docker: el puerto está ocupado o el contenedor no arranca

```bash
docker compose ps
docker compose logs backend
docker compose logs frontend
ss -ltnp | grep -E ':(8000|5173)'
```

Detén el proceso local o publica en otros puertos:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up -d --build
```

Si Compose rechaza `env_file` con `path`/`required`, actualiza a Compose v2.24+.

### Docker: el frontend no conecta con la API

```bash
docker compose ps
curl http://localhost:5173/api/v1/health
docker compose logs frontend
```

- El frontend usa `/api/v1` y Nginx lo reenvía a `backend:8000`.
- Verifica que el servicio se llame `backend` en `docker-compose.yml` y `frontend/nginx.conf`.
- Si el backend no está `healthy`, el frontend no arranca por `depends_on`.

### Docker: el backend arranca en modo muestra

No existe `data/processed/detections.csv` o el bind mount no lo ve:

```bash
ls -lh data/processed/
docker compose exec backend ls -lh /app/data/processed/
```

Ejecuta la ingesta dentro del contenedor o copia el dataset procesado al host.

### Docker: la ingesta escribió datos pero la API muestra los antiguos

El backend carga el CSV al arrancar:

```bash
docker compose restart backend
```

### Docker: reconstruir desde cero

```bash
docker compose down --rmi local
docker compose build --no-cache
docker compose up -d
```

---

## 15. Comandos rápidos

```bash
# Instalar todo desde cero
make install

# Backend en desarrollo
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend en desarrollo
cd frontend && npm run dev

# Pruebas backend
backend/.venv/bin/python -m pytest -q

# Integridad del dataset
backend/.venv/bin/python scripts/check_dataset.py

# Build de producción
cd frontend && npm run build

# Ingesta completa
backend/.venv/bin/python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw

# Docker: construir y levantar la pila
docker compose up -d --build

# Docker: estado, logs y parada
docker compose ps
docker compose logs -f
docker compose down

# Docker: pruebas e ingesta dentro del contenedor
docker compose run --rm backend python -m pytest -q
docker compose run --rm backend python scripts/check_dataset.py
docker compose run --rm backend python scripts/ingest_firms.py --start 2022-01-01 --end 2026-11-12 --keep-raw
docker compose restart backend

# Docker: puertos alternativos
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up -d --build
```

---

## 16. Documentación relacionada

- `README.md` — visión general, instalación y alcance.
- `docs/PROMPT_MAESTRO.md` — especificación original del reto.
- `docs/01-overview.md` — arquitectura y flujo de datos.
- `docs/02-data-model.md` — campos canónicos, confianza y manifiesto.
- `docs/03-scientific-methods.md` — métodos, agregaciones y anomalías.
- `docs/04-api.md` — endpoints y parámetros.
- `docs/05-runbook.md` — operación, actualización y resolución de problemas.
- `docs/06-docker.md` — Docker Compose, arquitectura de imágenes, datos y troubleshooting.
- `docs/07-ml-risk.md` — dataset, modelo, calibración, umbrales y limitaciones del riesgo ML.

---

## 17. Checklist para la demo

- [ ] Backend corriendo y `/api/v1/health` responde `200`.
- [ ] Frontend abierto en <http://localhost:5173> (o `docker compose up -d --build`).
- [ ] Dashboard muestra datos del periodo por defecto.
- [ ] Mapa carga puntos y contornos provinciales.
- [ ] Calendario permite navegar meses y filtrar un día.
- [ ] Comparador muestra MODIS y VIIRS con la advertencia de no comparabilidad.
- [ ] Anomalías responde a los parámetros interactivos.
- [ ] Hallazgos muestran evidencia, método y límite.
- [ ] Metodología muestra manifiesto, hashes y limitaciones.
- [ ] Exportación CSV descarga datos filtrados.
- [ ] La clave FIRMS no aparece en el navegador.
- [ ] Se explica claramente: detección ≠ incendio confirmado ≠ área quemada.
