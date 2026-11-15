# Integración del frontend de Incendios

La pantalla está implementada únicamente en `frontend/`. No se añadieron rutas ni se modificó el algoritmo del backend.

`useFireDashboard` consulta `GET /api/v1/fire-events?format=dashboard` mediante la configuración existente de la API. El contrato esperado es `{ meta, data }`, donde `data` cumple `FireDashboard` en `src/types/fire.ts`. La representación por defecto del endpoint es GeoJSON para el mapa; las tablas usan `format=json`.

Parámetros: `start_date`, `end_date`, `region_id`, `sensor`, `confidence`, `province_ids` (IDs separados por comas) y `granularity` (`day`, `week`, `month`). Los filtros afectan al feed, KPIs, serie y distribución provincial. La estacionalidad conserva el histórico disponible con los mismos filtros, sin limitarlo al rango de fechas de consulta. El servicio ordena eventos por severidad y FRP descendente.

`confirmed_critical` y `extreme_risk_cantons` deben ser `null` cuando no exista una fuente de confirmaciones o del modelo cantonal. Un cero significa una medición disponible sin casos, no ausencia de integración.

Si la ruta devuelve 404, el frontend usa ejemplos simulados de `src/data/fireDemo.ts` y muestra un aviso visible. Otros fallos muestran error y opción de reintentar; no se sustituyen silenciosamente con ejemplos. Las fechas simuladas se anclan al último día del dataset para permitir revisar los filtros iniciales.

El botón «Ver en mapa» transmite `focus_lat`, `focus_lon`, `event`, fechas del evento y provincia por URL. Para ejemplos añade `demo_event=1`. La vista del mapa enfoca esas coordenadas y añade un marcador de referencia etiquetado; no calcula polígonos ni riesgo.

Pruebas locales (Node 24):

```sh
node --experimental-strip-types tests/fireDemo.test.mjs
npm run build
npm run lint
```
