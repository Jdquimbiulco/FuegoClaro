# FuegoClaro

Base funcional para la armonización y exploración de detecciones de focos de calor **MODIS** y **VIIRS** en Ecuador, usando datos de [NASA FIRMS](https://firms.modaps.eosdis.nasa.gov/). Proyecto preparado para el reto *NASA Space Apps — Harmonization of MODIS and VIIRS Hot Spots*.

> **Aviso científico:** una detección de foco de calor **no** equivale a un incendio confirmado ni a superficie quemada. La ausencia de detecciones no implica ausencia de fuego. Los conteos MODIS y VIIRS no son directamente comparables como área ni gravedad.

---

## 📌 Organización del Equipo y Nuevas Mejoras
Para consultar la división de roles (**Gabo, ñoquito, Marcelo, Juanito, Erickoso y Mateogod**), checklists de trabajo y el plan de implementación de **Clustering (DBSCAN)** y **Modelo Predictivo de Susceptibilidad**, revisa:
👉 **[PLAN_EQUIPO_Y_MEJORAS.md](PLAN_EQUIPO_Y_MEJORAS.md)**

---

## 🚀 Código y Estructura Principal
El código fuente de la aplicación, backend, frontend y datasets se encuentra dentro del directorio [`Hackaton/`](Hackaton/):
- **Backend:** FastAPI + Pandas/NumPy + Shapely (`Hackaton/backend/`).
- **Frontend:** React + Vite + TypeScript + Tailwind + Leaflet + Recharts (`Hackaton/frontend/`).
- **Datos incluidos:** `Hackaton/data/processed/detections.csv`, GeoJSON provincial y muestras.
- **Guía de Inicio:** [`Hackaton/GUIA_DE_INICIO.md`](Hackaton/GUIA_DE_INICIO.md).
- **Documentación Técnica:** [`Hackaton/docs/`](Hackaton/docs/).
