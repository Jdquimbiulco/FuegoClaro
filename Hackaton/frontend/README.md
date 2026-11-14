# FuegoClaro — Frontend

Aplicación React + Vite + TypeScript + Tailwind para explorar detecciones de focos de calor MODIS/VIIRS de NASA FIRMS.

## Ejecución

```bash
npm install
cp .env.example .env   # opcional; por defecto apunta a http://localhost:8000/api/v1
npm run dev
```

Requiere el backend FastAPI corriendo en `http://localhost:8000` (ver README raíz).

## Comandos

- `npm run dev` — servidor de desarrollo.
- `npm run build` — type-check + build de producción.
- `npm run preview` — previsualizar el build.
- `npm run lint` — Oxlint.

## Estructura

- `src/pages/` — dashboard, mapa, calendario, comparador, anomalías, hallazgos, metodología.
- `src/components/` — layout, UI, gráficos y mapa Leaflet.
- `src/context/FiltersContext.tsx` — filtros globales sincronizados con la URL.
- `src/services/api.ts` — cliente HTTP; la MAP_KEY nunca llega al navegador.
- `src/types/api.ts` — contratos de la API.

La documentación completa está en `../docs/` y en el README raíz.
