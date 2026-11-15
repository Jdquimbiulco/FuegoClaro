# Diagnóstico local de memoria: ejecución bloqueada antes de optimizar

## Estado real

No se ha implementado la optimización del backend. No hay resultado AFTER ni afirmación de cumplimiento de 512 MiB. El worker autorizado `opencode/minimax-m3.1-flash-free` creó el banco de sondas y conservó las imágenes baseline, pero terminó con código 1: **Free usage limit reached**. No se usó modelo de pago ni otro proveedor. Log: `/home/erickobando/.hermes/cache/scratch/fuegoclaro-worker.log`.

El supervisor revisó los scripts, corrigió el guardado de respuestas JSON y la aceptación incorrecta de errores iguales en el comparador; ejecutó las pruebas descritas abajo. Solo se agregaron scripts/documentación, sin modificar código científico, UI, datos ni geometrías. Sin push/deploy, cambios de credenciales ni servicio risk-refresh.

## Baseline medido

Imagen: `fuegoclaro-pruebas-backend:baseline`, ID `sha256:84a9c71361b4eda2f8742b59fec401839a41d5bda5592b8af5fe9a3f17875785`.

- Contenedor `fuegoclaro-pruebas-reference`, `127.0.0.1:8011`, límite 4 GiB y memory-swap igual (sin swap).
- 49 sondas estáticas + detalle dinámico: **50/50 HTTP 200**. Duración acumulada de requests 97100.783 ms; máximo individual 35792.756 ms.
- Repetición concurrente, 6 trabajadores y 2 rondas: **99/99 HTTP 200**. Tiempo de ejecución del proceso medido 77.572 s; duración máxima de request 66021.895 ms. Pico cgroup **2773434368 bytes**. Sin OOM.
- Contenedor `fuegoclaro-pruebas-baseline512`, `127.0.0.1:8012`, memoria y memory-swap **536870912 bytes**. Tras comprobar health HTTP 200, misma concurrencia: **6 éxitos y 93 fallos**, proceso del servidor terminado con **OOMKilled=true y ExitCode=137**. Pico cgroup **536870912 bytes**, máximo current muestreado **536530944 bytes**. Medición cada 0.1 s; el máximo current es muestreado, memory.peak viene del kernel.
- Suite pytest baseline: **38 passed, 38 warnings in 7.03s**. Advertencias preexistentes de Starlette/httpx y fragmentación pandas.

Las sondas incluyen detecciones JSON/GeoJSON con limit=20000, regiones, susceptibilidad, SNAP, alertas ambientales, dashboard de incendios, analítica, filtros e histórico. Fechas anuales 2025-11-13 a 2026-11-12. Datos reales: 116729 registros.

## Hallazgo adicional de determinismo

Comparar primera corrida con la repetición del mismo baseline da **49/50 hashes iguales**: `/meta` cambia porque aparecen campos `cantons[].count` después de otras consultas. No es timestamp y NO fue ignorado. Investigar mutación compartida antes de exigir equivalencia ciega entre estados fríos/calientes. No se cambió el backend para esconder esta diferencia.

## Evidencia y reproducción

Directorio absoluto: `/home/erickobando/.hermes/cache/scratch/fuegoclaro-mem/evidence/`.

- `baseline-4g-results.json`: resultados secuenciales.
- `responses/baseline-4g/*.json`: respuestas canónicas de las sondas estáticas JSON; no se conservan cuerpos no JSON. El detalle dinámico tiene hash en el informe pero no cuerpo conservado.
- `baseline-4g-concurrent-results.json`, `baseline-4g-memory.json`: concurrencia y muestras cgroup.
- `baseline-512-ready-concurrent-results.json`, `baseline-512-ready-memory.json`: fallo OOM después de health listo.
- `baseline-repeat-comparison.json`: discrepancia real de meta.
- `pytest-baseline.log`: salida completa pytest.
- Los archivos `baseline-512-concurrent-results.json` y `baseline-512-memory.json` SIN `ready` son una primera ejecución inválida por falta de espera de arranque: NO usar como prueba de memoria.

Desde `Hackaton/`, con el contenedor de referencia listo:

```sh
python3 scripts/bench/run_probes.py --base-url http://127.0.0.1:8011 --label referencia-nueva --out-dir /home/erickobando/.hermes/cache/scratch/fuegoclaro-mem/evidence --concurrency 1 --timeout 120
python3 scripts/bench/measure_container.py --container fuegoclaro-pruebas-reference --out /home/erickobando/.hermes/cache/scratch/fuegoclaro-mem/evidence/memoria-nueva.json -- python3 scripts/bench/run_probes.py --base-url http://127.0.0.1:8011 --label concurrente-nueva --out-dir /home/erickobando/.hermes/cache/scratch/fuegoclaro-mem/evidence --concurrency 6 --repeat 2 --timeout 120 --no-save-bodies
```

`measure_container.py` usa cgroup v2 del host Linux y captura solo estado/límites Docker, no variables de entorno. Esperar health antes de invocarlo. Los scripts `bench_isolated.sh` y `cgroup_snapshot.sh` del worker son BORRADORES no validados end-to-end: el shell presupone scripts dentro de la imagen baseline y puede interrumpirse antes de capturar estado al fallar una sonda. Usar los comandos Python anteriores, no ese shell, para las evidencias citadas.

## Pendiente por bloqueo

Implementación optimizada, TDD de los cambios de producción, comparación BEFORE/AFTER, supervivencia 512 MiB, prueba 0.1 CPU, build frontend nuevo y verificación de UI. Ninguno se afirma completado. El modelo gratuito agotó la cuota antes de escribir código de producción; requiere cuota disponible o autorización de otra modalidad. Los contenedores ajenos `fuegoclaro-backend-1` y `fuegoclaro-frontend-1` no se tocaron. El secreto preexistente indicado en render.yaml requiere rotación por el propietario; no se imprimió ni modificó.
