# Riesgo predictivo y alertas ambientales

## Qué publica el sistema

El mapa combina cuatro capas independientes:

1. Detecciones históricas NASA FIRMS.
2. Susceptibilidad predictiva por celdas de `0.1°` (~11 km).
3. Áreas protegidas del Sistema Nacional de Áreas Protegidas (SNAP).
4. Alertas ambientales efímeras.

El riesgo estima la probabilidad de una detección térmica durante el horizonte
seleccionado; no confirma incendios, afectación de un área ni superficie quemada.

## Regla de alerta

Se publica una alerta prioritaria si ocurre una de estas condiciones:

- una celda de riesgo **Alto** o **Extremo** intersecta un polígono SNAP;
- un evento térmico `alerta_roja` contiene al menos una detección puntual dentro
  de un polígono SNAP.

El cruce observado usa los puntos reales de detección, no el *hull* del evento,
para evitar falsos positivos espaciales. Galápagos permanece visible en el mapa,
pero se excluye de alertas automáticas prioritarias por posibles anomalías de
origen volcánico.

Las alertas no se guardan en una base de datos: se recalculan al consultar el
endpoint con el último artefacto de riesgo publicado.

## Actualización configurable

El contenedor `risk-refresh` genera las capas al iniciar y luego repite el
proceso cada `SUSCEPTIBILITY_REFRESH_SECONDS`. El valor predeterminado es
`86400`, equivalente a una vez al día.

En `backend/.env` agrega o modifica:

```env
SUSCEPTIBILITY_REFRESH_SECONDS=86400
SUSCEPTIBILITY_HORIZONS=0,1,3,7
```

`SUSCEPTIBILITY_REFRESH_SECONDS` debe ser al menos `300`. Por ejemplo, para
actualizar cada 12 horas usa `43200`. Tras cambiarlo, recrea solo el job:

```powershell
docker compose up -d --build risk-refresh
```

La actualización se puede lanzar manualmente sin esperar al programador:

```powershell
docker compose run --rm risk-refresh python /app/scripts/build_susceptibility_map.py
```

Los artefactos se escriben en `data/processed/susceptibility/latest-h{N}.geojson`.
El horizonte 7 también se copia a `data/processed/susceptibility.json` por
compatibilidad con consumidores anteriores.

## API

- `GET /api/v1/susceptibility?level=cell&window_days=7`
- `GET /api/v1/protected-areas`
- `GET /api/v1/environmental-alerts?window_days=7`

Los endpoints incluyen metadatos de generación y avisos metodológicos. El mapa
debe mostrar la fecha real del artefacto, no presentarlo como monitoreo en vivo.
