# Visión general y arquitectura

FuegoClaro es una base funcional para explorar detecciones de focos de calor MODIS y VIIRS en Ecuador. El objetivo es **armonizar** ambos productos sin ocultar sus diferencias y ofrecer análisis trazables.

## Capas

1. **Ingesta** (`scripts/ingest_firms.py` + `backend/app/services/firms_client.py`): descarga NASA FIRMS por producto y bloques de 5 días, con pausas/reintentos y fallo estricto ante cuota o respuesta inválida.
2. **Dominio** (`backend/app/domain/`): normalización, validación, agregaciones, comparación, anomalías e insights.
3. **Servicio de datos** (`backend/app/services/data_store.py`): carga CSV/manifiesto, modo real/muestra/vacío y filtros comunes.
4. **API** (`backend/app/api/v1/`): endpoints REST y exportación CSV.
5. **Frontend** (`frontend/src/`): React + Vite + Tailwind; estado de filtros en URL; Leaflet y Recharts.

## Flujo de datos

```
NASA FIRMS Area API
        │  (MAP_KEY solo backend)
        ▼
CSV crudo por producto ──► normalización canónica ──► validación
        │                                      │
        │                                      ├─► recorte provincial (Natural Earth)
        │                                      ├─► región/provincia + hora local
        │                                      └─► deduplicación
        ▼
data/processed/detections.csv + manifest.json
        │
        ├─► muestra offline (data/samples/)
        └─► API FastAPI ──► frontend
```

## Módulos de la interfaz

- **Dashboard**: indicadores, serie mensual, confianza, regiones/provincias y últimas detecciones.
- **Mapa**: clustering visual, popups, contornos provinciales y exportación.
- **Calendario**: conteo diario, intensidad relativa, desglose por sensor y filtro por día.
- **Comparador**: MODIS vs VIIRS en el mismo periodo, cobertura, confianza y series.
- **Anomalías**: parámetros interactivos, z-score, FDR y evidencia por día.
- **Hallazgos**: tarjetas deterministas con evidencia, método y límite.
- **Metodología**: fuentes, pipeline, confianza, estadística, API y comandos.

## Principios

- No inventar datos ni rellenar vacíos.
- Separar detección de incendio confirmado y de área quemada.
- Documentar procedencia, transformaciones y limitaciones.
- Mantener la clave de FIRMS fuera del navegador.
