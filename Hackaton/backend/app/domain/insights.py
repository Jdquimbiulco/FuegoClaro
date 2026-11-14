"""Centro de hallazgos: textos deterministas construidos sobre resultados calculados.

No se usa un LLM para calcular ni inventar cifras. Cada hallazgo incluye la
evidencia numérica y el método que lo respalda.
"""

from __future__ import annotations

import pandas as pd

from app.domain.aggregation import build_summary, monthly_peaks, region_label
from app.domain.anomalies import detect_anomalies
from app.domain.comparison import build_comparison
from app.domain.models import FilterSpec

MONTHS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre",
}


def _n(value: int | float | None) -> str:
    if value is None:
        return "sin dato"
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:,}".replace(",", ".")


def _sensor_label(sensor: str | None) -> str:
    if not sensor or sensor == "all":
        return "MODIS + VIIRS"
    return sensor


def build_insights(df: pd.DataFrame, spec: FilterSpec, *, granularity: str = "month") -> dict:
    summary = build_summary(df, spec)
    comparison = build_comparison(df, spec, granularity=granularity)
    anomalies = detect_anomalies(df, spec, max_results=8)
    peaks = monthly_peaks(df, spec)

    region = summary["region"]["name"]
    period = summary["period"]
    sensor_label = _sensor_label(spec.sensor)
    base = {
        "region": summary["region"],
        "period": period,
        "sensor": sensor_label,
    }
    insights: list[dict] = []

    if summary["total"] == 0:
        return {
            "summary": {"total": 0, "generated": 0},
            "period": period,
            "region": summary["region"],
            "insights": [],
            "notes": ["No hay detecciones para los filtros seleccionados; no se generan hallazgos."],
            "method": "Los hallazgos se generan solo a partir de agregaciones con datos.",
        }

    # 1. Volumen y reparto por sensor.
    by_sensor = summary["by_sensor"]
    sensor_text = ", ".join(f"{item['sensor']}: {_n(item['count'])} ({item['share'] * 100:.0f}%)" for item in by_sensor)
    insights.append(
        {
            "id": "volumen",
            "title": f"{_n(summary['total'])} detecciones de focos de calor en {region}",
            "text": (
                f"Entre {period['start']} y {period['end']} se registraron {_n(summary['total'])} "
                f"detecciones. Reparto por sensor: {sensor_text}. "
                f"Hubo actividad detectada en {_n(summary['active_days'])} de {_n(summary['days_in_period'])} días "
                f"({summary['detections_per_day']:.2f} detecciones/día en promedio)."
            ),
            "tone": "info",
            "indicator": "conteo de detecciones",
            "value": _n(summary["total"]),
            "method": "Conteo de registros por fecha local de adquisición.",
            "evidence": [
                {"label": "Total", "value": _n(summary["total"])},
                {"label": "Días con detecciones", "value": _n(summary["active_days"])},
                *[{"label": item["sensor"], "value": _n(item["count"])} for item in by_sensor],
            ],
            "caveat": "Una detección no es un incendio confirmado ni mide superficie quemada.",
            **base,
        }
    )

    # 2. Brecha entre sensores.
    counts = {item["sensor"]: item["count"] for item in by_sensor}
    if counts.get("MODIS") and counts.get("VIIRS"):
        modis, viirs = counts["MODIS"], counts["VIIRS"]
        ratio = viirs / modis
        insights.append(
            {
                "id": "brecha_sensores",
                "title": "VIIRS y MODIS no detectan el mismo número de píxeles",
                "text": (
                    f"Se registraron {_n(viirs)} detecciones VIIRS y {_n(modis)} MODIS "
                    f"(≈{ratio:.1f} veces más VIIRS). Esto es esperable: VIIRS tiene píxeles de ~375 m "
                    "frente a ~1 km de MODIS y distinta sensibilidad. No implica que el área afectada sea "
                    f"{ratio:.1f} veces mayor."
                ),
                "tone": "warning",
                "indicator": "razón de conteos VIIRS/MODIS",
                "value": f"{ratio:.2f}×",
                "method": "Cociente entre conteos de detecciones del mismo periodo y región.",
                "evidence": [
                    {"label": "VIIRS", "value": _n(viirs)},
                    {"label": "MODIS", "value": _n(modis)},
                    {"label": "Razón", "value": f"{ratio:.2f}×"},
                ],
                "caveat": "Los conteos no son directamente comparables como superficie ni gravedad.",
                **base,
            }
        )

    # 3. Pico temporal.
    if peaks:
        month_number = int(peaks["month"].split("-")[1])
        insights.append(
            {
                "id": "pico_temporal",
                "title": "Concentración temporal de las detecciones",
                "text": (
                    f"El mes con más detecciones fue {MONTHS_ES.get(month_number, peaks['month'])} "
                    f"de {peaks['month'].split('-')[0]} con {_n(peaks['month_count'])} registros. "
                    f"El día con mayor conteo fue {peaks['day']} con {_n(peaks['day_count'])} detecciones."
                ),
                "tone": "info",
                "indicator": "conteo mensual y diario máximo",
                "value": f"{_n(peaks['month_count'])} en {peaks['month']}",
                "method": "Agregación por mes y por día local; se reporta el máximo observado.",
                "evidence": [
                    {"label": "Mes pico", "value": f"{peaks['month']} ({_n(peaks['month_count'])})"},
                    {"label": "Día pico", "value": f"{peaks['day']} ({_n(peaks['day_count'])})"},
                ],
                "caveat": "Un pico de detecciones puede reflejar condiciones de observación, no solo más fuego.",
                **base,
            }
        )

    # 4. Concentración regional.
    if len(summary["by_region"]) > 1:
        top = summary["by_region"][0]
        insights.append(
            {
                "id": "concentracion_regional",
                "title": f"La mayor concentración se observó en {top['region']}",
                "text": (
                    f"{top['region']} acumuló {_n(top['count'])} detecciones "
                    f"({top['share'] * 100:.0f}% del total del periodo). "
                    f"La segunda región fue {summary['by_region'][1]['region']} "
                    f"con {_n(summary['by_region'][1]['count'])}."
                ),
                "tone": "info",
                "indicator": "participación regional en el total",
                "value": f"{top['share'] * 100:.0f}% en {top['region']}",
                "method": "Conteo por región natural asignada mediante geometrías provinciales.",
                "evidence": [
                    {"label": item["region"], "value": _n(item["count"])}
                    for item in summary["by_region"][:4]
                ],
                "caveat": "La concentración de detecciones no equivale a mayor área quemada.",
                **base,
            }
        )

    # 5. Calidad de las detecciones.
    low = summary["by_confidence"].get("low", 0)
    if low:
        share = low / summary["total"] * 100
        insights.append(
            {
                "id": "confianza",
                "title": "Proporción de detecciones de confianza baja",
                "text": (
                    f"{_n(low)} detecciones ({share:.0f}%) tienen confianza baja. "
                    "Pueden estar asociadas a brillo solar, calor industrial u otras fuentes; "
                    "para un análisis conservador se recomienda comparar con el filtro nominal/alto."
                ),
                "tone": "warning" if share >= 15 else "info",
                "indicator": "porcentaje de confianza baja",
                "value": f"{share:.0f}%",
                "method": "Clasificación MODIS 0–100 (low <30, nominal 30–79, high ≥80) y VIIRS l/n/h.",
                "evidence": [
                    {"label": level, "value": _n(value)}
                    for level, value in summary["by_confidence"].items()
                ],
                "caveat": "Los esquemas de confianza de MODIS y VIIRS no son directamente equivalentes.",
                **base,
            }
        )

    # 6. Anomalía más relevante.
    top_anomaly = anomalies["anomalies"][0] if anomalies["anomalies"] else None
    if top_anomaly:
        direction = "por encima" if top_anomaly["direction"] == "high" else "por debajo"
        insights.append(
            {
                "id": "anomalia",
                "title": f"Conteo inusual {direction} de la referencia en {top_anomaly['region']}",
                "text": (
                    f"El {top_anomaly['date']} se observaron {_n(top_anomaly['observed'])} detecciones "
                    f"en {top_anomaly['region']} ({top_anomaly['sensor']}), frente a una media histórica "
                    f"de {_n(top_anomaly['baseline_mean'])} para fechas comparables "
                    f"(z={top_anomaly['z_score']}, q={top_anomaly['q_value']:.4f})."
                ),
                "tone": "critical" if top_anomaly["direction"] == "high" else "info",
                "indicator": "z-score de conteo diario con control FDR",
                "value": f"z={top_anomaly['z_score']}",
                "method": anomalies["method"],
                "evidence": [
                    {"label": "Observado", "value": _n(top_anomaly["observed"])},
                    {"label": "Media línea base", "value": _n(top_anomaly["baseline_mean"])},
                    {"label": "Días de línea base", "value": _n(top_anomaly["baseline_days"])},
                    {"label": "q-valor", "value": f"{top_anomaly['q_value']:.4f}"},
                ],
                "caveat": "La anomalía describe el conteo de detecciones, no la causa ni la superficie afectada.",
                **base,
            }
        )
    else:
        insights.append(
            {
                "id": "anomalia",
                "title": "Sin anomalías estadísticas destacadas",
                "text": (
                    "Con el umbral y el control de falsos descubrimientos configurados, "
                    "no se identificaron días con conteos inusuales respecto a la referencia histórica. "
                    "Esto no descarta eventos: la sensibilidad depende de la línea base y de la cobertura."
                ),
                "tone": "info",
                "indicator": "ausencia de anomalías significativas",
                "value": "0",
                "method": anomalies["method"],
                "evidence": [{"label": "Pruebas realizadas", "value": _n(anomalies["summary"]["tests"])}],
                "caveat": "La ausencia de anomalía estadística no equivale a ausencia de actividad.",
                **base,
            }
        )

    # 7. Intensidad radiativa.
    if summary["frp"]["sum"] is not None:
        insights.append(
            {
                "id": "frp",
                "title": "Intensidad radiativa acumulada (FRP)",
                "text": (
                    f"La suma de FRP de las detecciones con dato válido fue {_n(summary['frp']['sum'])} MW "
                    f"(media {_n(summary['frp']['mean'])} MW; máximo {_n(summary['frp']['max'])} MW). "
                    "El FRP estima energía radiativa del píxel; no es superficie quemada."
                ),
                "tone": "info",
                "indicator": "Fire Radiative Power (MW)",
                "value": f"{_n(summary['frp']['sum'])} MW",
                "method": "Suma y estadísticas de FRP de los registros con valor válido.",
                "evidence": [
                    {"label": "FRP total", "value": f"{_n(summary['frp']['sum'])} MW"},
                    {"label": "FRP medio", "value": f"{_n(summary['frp']['mean'])} MW"},
                    {"label": "Registros con FRP", "value": _n(summary["frp"]["valid"])},
                ],
                "caveat": "El FRP depende de la detección y del píxel; no se traduce directamente a área quemada.",
                **base,
            }
        )

    return {
        "summary": {
            "total": summary["total"],
            "generated": len(insights),
            "anomalies_flagged": anomalies["summary"]["flagged"],
        },
        "period": period,
        "region": summary["region"],
        "insights": insights,
        "notes": [
            "Los textos se generan con reglas y cifras calculadas; no se usa IA para inventar resultados.",
            "Cada hallazgo incluye indicador, valor, método y limitaciones.",
        ],
        "method": "Plantillas deterministas sobre agregaciones, comparación y anomalías calculadas.",
    }
