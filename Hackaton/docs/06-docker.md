# Docker: ejecución reproducible

FuegoClaro se puede ejecutar con Docker Compose en cualquier máquina que tenga Docker. La pila incluye:

- **backend**: FastAPI + Pandas/NumPy/Shapely, servido con Uvicorn en el puerto interno `8000`.
- **frontend**: build estático de Vite servido por Nginx en el puerto interno `80`, con proxy interno hacia `/api/`.
- **data**: volumen bind montado desde `./data` para persistir el dataset, los CSV crudos y los manifiestos.

La clave de NASA FIRMS se inyecta en runtime desde `backend/.env`; **no se hornea en las imágenes**.

---

## 1. Requisitos

- Docker Engine 24+ o Docker Desktop.
- Docker Compose v2.24+ (por el `env_file` opcional).
- Puertos libres: `8000` (API) y `5173` (web), salvo que los cambies.

Verifica:

```bash
docker --version
docker compose version
```

---

## 2. Configurar la clave FIRMS

```bash
cd /ruta/al/proyecto
cp backend/.env.example backend/.env
```

Edita `backend/.env`:

```dotenv
FIRMS_MAP_KEY=tu_clave_de_nasa_firms
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Si no defines la clave, la app igual funciona para **consultar** un dataset ya existente o la muestra; la clave solo es necesaria para **volver a descargar** datos desde NASA FIRMS.

---

## 3. Levantar la pila

```bash
docker compose up -d --build
```

Servicios resultantes:

| Servicio | URL |
| --- | --- |
| Aplicación web | <http://localhost:5173> |
| API directa | <http://localhost:8000/api/v1> |
| Documentación de la API | <http://localhost:8000/docs> |
| Health check | <http://localhost:8000/api/v1/health> |

El frontend consume la API mediante `http://localhost:5173/api/v1/...`, que Nginx reenvía al backend. Esto evita problemas de CORS y permite desplegar la web y la API como un solo origen.

Ver estado:

```bash
docker compose ps
docker compose logs -f
```

Detener:

```bash
docker compose down
```

Las imágenes y el volumen de datos se conservan. Para eliminar también las imágenes:

```bash
docker compose down --rmi local
```

---

## 4. Cómo se resuelven los datos

El `docker-compose.yml` monta:

```yaml
volumes:
  - ./data:/app/data
```

Por lo tanto:

- Si `data/processed/detections.csv` existe, el backend arranca en **modo real** con ese dataset.
- Si no existe, pero `data/samples/detections_sample.csv` está presente (está versionado), arranca en **modo muestra**.
- Si no hay ninguno, arranca en **modo vacío** y la interfaz lo indica sin inventar cifras.

La imagen del backend también copia `data/` en el build, así que un `docker run` sin volumen puede funcionar de forma autocontenida. En Compose, el bind mount tiene prioridad.

### Descargar datos reales dentro de Docker

Con `backend/.env` configurado:

```bash
docker compose run --rm backend python scripts/ingest_firms.py \
  --start 2022-01-01 \
  --end 2026-11-12 \
  --keep-raw
```

Al terminar, reinicia el backend para que cargue el nuevo CSV:

```bash
docker compose restart backend
```

Consideraciones:

- La ingesta respeta pausas para no exceder la cuota de FIRMS.
- Si FIRMS falla o rechaza la clave, **no se publica un dataset parcial**.
- No ejecutes dos ingestas en paralelo.
- Los archivos quedan en `./data/processed/` y `./data/raw/` del host.

### Verificar integridad

```bash
docker compose run --rm backend python scripts/check_dataset.py
```

---

## 5. Pruebas dentro de Docker

```bash
docker compose run --rm backend python -m pytest -q
```

Resultado esperado: `28 passed`.

También puedes validar la API:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/meta
curl http://localhost:8000/api/v1/stats/summary
```

---

## 6. Cambiar puertos

Si los puertos por defecto están ocupados:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up -d --build
```

- Web: <http://localhost:5180>
- API: <http://localhost:8010/api/v1>
- Docs: <http://localhost:8010/docs>

El proxy interno del frontend sigue funcionando porque usa el nombre de servicio `backend` dentro de la red de Compose, no el puerto publicado.

---

## 7. Arquitectura de las imágenes

```text
Navegador
   │
   ├── http://localhost:5173/            → Nginx → /usr/share/nginx/html (SPA)
   └── http://localhost:5173/api/v1/...  → Nginx → http://backend:8000/api/v1/...
                                                        │
                                                        ▼
                                              FastAPI + Uvicorn
                                                        │
                                                        ▼
                                              /app/data (bind mount ./data)
```

### Backend

- Base: `python:3.12-slim`.
- Instala `requirements.txt` y `requirements-dev.txt`.
- Copia `backend/`, `scripts/`, `tests/`, `pytest.ini` y `data/`.
- `PYTHONPATH=/app/backend`.
- Healthcheck contra `/api/v1/health`.
- Usuario root dentro del contenedor para facilitar la escritura en el bind mount local. Para producción, considera un usuario no-root y un volumen con permisos explícitos.

### Frontend

- Etapa 1: `node:22-alpine`, `npm ci`, `npm run build` con `VITE_API_BASE_URL=/api/v1`.
- Etapa 2: `nginx:1.27-alpine` sirviendo `dist/` y haciendo proxy de `/api/`.
- Fallback SPA: cualquier ruta desconocida devuelve `index.html`.
- Caché larga para assets con hash.

---

## 8. Variables de entorno

| Variable | Dónde | Uso |
| --- | --- | --- |
| `FIRMS_MAP_KEY` | `backend/.env` | Clave de NASA FIRMS para la ingesta. |
| `CORS_ORIGINS` | `backend/.env` | Orígenes permitidos si se consume la API directamente. |
| `VITE_API_BASE_URL` | build del frontend | En Docker se fija a `/api/v1`. |
| `BACKEND_PORT` | shell / Compose | Puerto publicado del backend. Default `8000`. |
| `FRONTEND_PORT` | shell / Compose | Puerto publicado del frontend. Default `5173`. |

`backend/.env` está en `.gitignore` y también se excluye del contexto de build con `.dockerignore`. La clave no queda dentro de las imágenes.

---

## 9. Solución de problemas

### `docker compose up` falla porque el puerto está ocupado

```bash
ss -ltnp | grep -E ':(8000|5173)'
```

Detén el proceso local o cambia los puertos:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=5180 docker compose up -d
```

### El frontend no conecta con la API

```bash
docker compose ps
docker compose logs backend
docker compose logs frontend
curl http://localhost:5173/api/v1/health
```

Si el proxy falla, revisa que el servicio se llame `backend` en `docker-compose.yml` y en `frontend/nginx.conf`.

### El backend arranca en modo muestra

No existe `data/processed/detections.csv` o el bind mount no está viendo el archivo. Verifica:

```bash
ls -lh data/processed/
docker compose exec backend ls -lh /app/data/processed/
```

Ejecuta la ingesta o copia el dataset procesado.

### `Invalid MAP_KEY` durante la ingesta

- Verifica la clave en `backend/.env`.
- Espera unos minutos: FIRMS limita transacciones.
- No ejecutes ingestas paralelas.
- El dataset anterior permanece intacto.

### La ingesta escribió datos pero la API sigue mostrando los antiguos

El backend carga el CSV al arrancar y lo mantiene en memoria:

```bash
docker compose restart backend
```

### Quiero reconstruir desde cero

```bash
docker compose down --rmi local
docker compose build --no-cache
docker compose up -d
```

---

## 10. Notas para producción

- Coloca la app detrás de HTTPS (por ejemplo, con un reverse proxy externo o Traefik).
- No publiques el puerto del backend si solo se consume a través del frontend; usa `expose` en lugar de `ports`.
- Usa un usuario no-root y permisos explícitos para el volumen de datos.
- Limita el acceso a `backend/.env` y rota la clave si se filtra.
- Considera separar el dataset en un volumen nombrado o almacenamiento externo.
- Revisa el tamaño del bundle del frontend (~985 kB); se puede optimizar con code-splitting.
