# Áreas protegidas SNAP de Ecuador

## Archivo

- **Archivo:** `protected_areas_snap_ec.geojson`
- **Ubicación:** `data/regions/`
- **Formato:** GeoJSON
- **CRS de salida:** EPSG:4326 - WGS 84
- **Contenido:** 81 polígonos de áreas protegidas.

## Campos principales

| Campo | Descripción |
| --- | --- |
| `nam` | Nombre del área protegida. |
| `map` | Categoría de manejo, por ejemplo, Parque Nacional. |
| `csnap` | Código de la capa SNAP. |
| `subap` | Subsistema de área protegida. |

## Verificación

Se verificó que la capa contiene el siguiente registro:

- `nam`: `PODOCARPUS`
- `map`: `PARQUE NACIONAL`

## Procedencia

- **Fecha de descarga y exportación:** 14 de noviembre de 2026.
- **Fuente declarada:** capa SNAP descargada del portal ambiental oficial.
- **CRS de la capa original:** EPSG:32717 - WGS 84 / UTM zona 17S.
- **Transformación aplicada:** exportación desde QGIS a GeoJSON en EPSG:4326 para su consumo en la web.

## Uso en FuegoClaro

El backend debe cruzar la geometría de cada evento de incendio con los polígonos de esta capa.

- Si un evento intersecta un polígono, debe incluir el nombre y la categoría del área y asignar `ecological_impact: "critical"`.
- Si un evento queda fuera, no debe llevar la etiqueta de impacto ecológico crítico.
- La proximidad sin intersección debe tratarse como contexto de cercanía, no como ocurrencia dentro de un área protegida.

Esta capa representa el SNAP. Las capas municipales o de otros contextos ecológicos, como Ilaló, deben mantenerse separadas y etiquetarse con su categoría real.
