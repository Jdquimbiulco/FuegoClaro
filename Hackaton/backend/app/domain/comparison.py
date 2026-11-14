"""Comparación MODIS vs VIIRS con advertencias de comparabilidad."""

from __future__ import annotations

import pandas as pd

from app.domain.aggregation import build_timeseries, region_label
from app.domain.models import FilterSpec
from app.services.data_store import apply_filters
from app.utils.time import days_between


def _sensor_stats(group: pd.DataFrame, days: int, total: int) -> dict:
    active_days = int(group["acq_date_local"].nunique())
    daily = group.groupby("acq_date_local").size()
    frp = group["frp"].dropna()
    return {
        "sensor": str(group["sensor"].iloc[0]),
        "count": int(len(group)),
        "share": round(len(group) / total, 4) if total else 0.0,
        "active_days": active_days,
        "coverage": round(active_days / days, 4) if days else 0.0,
        "mean_daily": round(len(group) / days, 2) if days else 0.0,
        "max_daily": int(daily.max()) if not daily.empty else 0,
        "frp_sum": round(float(frp.sum()), 2) if not frp.empty else None,
        "frp_mean": round(float(frp.mean()), 2) if not frp.empty else None,
        "confidence": {str(key): int(value) for key, value in group["confidence_level"].value_counts().items()},
        "satellites": [
            {"satellite": str(key), "count": int(value)}
            for key, value in group["satellite"].value_counts().items()
        ],
        "products": [
            {"product": str(key), "count": int(value)}
            for key, value in group["source_product"].value_counts().items()
        ],
    }


def build_comparison(df: pd.DataFrame, spec: FilterSpec, granularity: str = "month") -> dict:
    filtered = apply_filters(df, spec)
    days = days_between(spec.start_date, spec.end_date)
    total = int(len(filtered))
    result = {
        "period": {"start": spec.start_date, "end": spec.end_date, "days": days},
        "region": {"id": spec.region_id or "ecuador", "name": region_label(spec.region_id)},
        "total": total,
        "by_sensor": [],
        "by_region": [],
        "series": [],
        "granularity": granularity,
        "count_ratio": None,
        "notes": [],
    }
    if filtered.empty:
        return result

    for _, group in filtered.groupby("sensor"):
        result["by_sensor"].append(_sensor_stats(group, days, total))
    result["by_sensor"].sort(key=lambda item: item["count"], reverse=True)

    region_rows = []
    for (region_id, sensor), group in filtered.groupby(["region_id", "sensor"]):
        region_rows.append(
            {
                "region_id": region_id,
                "region": region_label(region_id),
                "sensor": sensor,
                "count": int(len(group)),
            }
        )
    result["by_region"] = region_rows

    timeseries = build_timeseries(df, spec, granularity=granularity)
    result["series"] = timeseries["series"]

    counts = {item["sensor"]: item["count"] for item in result["by_sensor"]}
    modis = counts.get("MODIS", 0)
    viirs = counts.get("VIIRS", 0)
    if modis and viirs:
        result["count_ratio"] = {
            "viirs_over_modis": round(viirs / modis, 2),
            "interpretation": (
                f"En el periodo se registraron {viirs:,} detecciones VIIRS y {modis:,} MODIS "
                f"(≈{viirs / modis:.1f}× más VIIRS)."
            ),
        }

    result["notes"] = [
        "VIIRS tiene píxeles de ~375 m y MODIS de ~1 km: una misma fuente de calor puede generar distinto número de píxeles detectados.",
        "Los sensores tienen sensibilidad, algoritmos de confianza y horarios de pasada distintos; los conteos no miden superficie quemada.",
        "La diferencia de conteos no debe interpretarse como diferencia directa de área afectada ni de gravedad.",
        "Las detecciones de confianza baja son más frecuentes en ciertas condiciones (p. ej. brillo solar); compara desglosando por confianza.",
        "Si el periodo mezcla productos de procesamiento estándar (SP) y tiempo casi real (NRT), pueden existir diferencias de versión.",
    ]
    return result
