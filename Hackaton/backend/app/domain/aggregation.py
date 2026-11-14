"""Agregaciones temporales y espaciales para dashboard, calendario y series."""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.domain.models import FilterSpec, NATURAL_REGIONS, PROVINCES
from app.services.data_store import apply_filters
from app.utils.geo import province_slug
from app.utils.time import days_between, month_bounds

REGION_NAMES = {key: value["name"] for key, value in NATURAL_REGIONS.items()}
PROVINCE_NAMES = {province_slug(iso): name for iso, (name, _) in PROVINCES.items()}


def region_label(region_id: str | None) -> str:
    if not region_id or region_id in ("all", "ecuador"):
        return "Ecuador"
    if region_id in REGION_NAMES:
        return REGION_NAMES[region_id]
    if region_id in PROVINCE_NAMES:
        return PROVINCE_NAMES[region_id]
    if region_id in PROVINCES:
        return PROVINCES[region_id][0]
    return region_id.replace("-", " ").title()


def _share(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _numeric(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 2)


def build_summary(df: pd.DataFrame, spec: FilterSpec) -> dict:
    filtered = apply_filters(df, spec)
    total = int(len(filtered))
    days = days_between(spec.start_date, spec.end_date)
    period = {"start": spec.start_date, "end": spec.end_date, "days": days}
    result = {
        "period": period,
        "region": {"id": spec.region_id or "ecuador", "name": region_label(spec.region_id)},
        "sensor_filter": spec.sensor or "all",
        "total": total,
        "active_days": 0,
        "days_in_period": days,
        "detections_per_day": 0.0,
        "by_sensor": [],
        "by_confidence": {},
        "by_region": [],
        "by_province": [],
        "by_daynight": {},
        "frp": {"sum": None, "mean": None, "max": None, "valid": 0},
        "date_range": {"start": None, "end": None},
        "notes": [],
    }
    if filtered.empty:
        return result

    result["date_range"] = {
        "start": str(filtered["acq_date_local"].min()),
        "end": str(filtered["acq_date_local"].max()),
    }
    result["active_days"] = int(filtered["acq_date_local"].nunique())
    result["detections_per_day"] = round(total / days, 2) if days else 0.0
    result["by_confidence"] = {str(key): int(value) for key, value in filtered["confidence_level"].value_counts().items()}
    result["by_daynight"] = {str(key): int(value) for key, value in filtered["daynight"].value_counts().items()}

    sensor_rows = []
    for sensor, group in filtered.groupby("sensor"):
        sensor_rows.append(
            {
                "sensor": sensor,
                "count": int(len(group)),
                "share": _share(len(group), total),
                "active_days": int(group["acq_date_local"].nunique()),
                "frp_sum": _numeric(group["frp"].sum()),
                "frp_mean": _numeric(group["frp"].mean()),
            }
        )
    result["by_sensor"] = sorted(sensor_rows, key=lambda item: item["count"], reverse=True)

    region_rows = []
    for region_id, group in filtered.groupby("region_id"):
        region_rows.append(
            {
                "region_id": region_id,
                "region": region_label(region_id),
                "count": int(len(group)),
                "share": _share(len(group), total),
            }
        )
    result["by_region"] = sorted(region_rows, key=lambda item: item["count"], reverse=True)

    province_rows = []
    for province_id, group in filtered.groupby("province_id"):
        province_rows.append(
            {
                "province_id": province_id,
                "province": str(group["province"].iloc[0]),
                "region_id": str(group["region_id"].iloc[0]),
                "count": int(len(group)),
                "share": _share(len(group), total),
            }
        )
    result["by_province"] = sorted(province_rows, key=lambda item: item["count"], reverse=True)[:10]

    frp = filtered["frp"].dropna()
    result["frp"] = {
        "sum": _numeric(frp.sum()) if not frp.empty else None,
        "mean": _numeric(frp.mean()) if not frp.empty else None,
        "max": _numeric(frp.max()) if not frp.empty else None,
        "valid": int(len(frp)),
    }

    notes = [
        "Una detección de foco de calor no equivale a un incendio confirmado ni a superficie quemada.",
        "La ausencia de detecciones no implica ausencia de fuego: nubes, humo y geometría de observación pueden ocultarlo.",
    ]
    low_share = _share(result["by_confidence"].get("low", 0), total)
    if low_share >= 0.15:
        notes.append(
            f"El {low_share * 100:.0f}% de las detecciones son de confianza baja; considera filtrar a nominal/alta."
        )
    result["notes"] = notes
    return result


def _period_column(filtered: pd.DataFrame, granularity: str) -> pd.Series:
    dates = pd.to_datetime(filtered["acq_date_local"], errors="coerce")
    if granularity == "month":
        return dates.dt.strftime("%Y-%m")
    if granularity == "week":
        iso = dates.dt.isocalendar()
        return iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    return filtered["acq_date_local"].astype(str)


def build_timeseries(df: pd.DataFrame, spec: FilterSpec, granularity: str = "day") -> dict:
    filtered = apply_filters(df, spec)
    result = {
        "granularity": granularity,
        "period": {"start": spec.start_date, "end": spec.end_date},
        "series": [],
        "totals_by_sensor": {},
        "notes": ["Serie basada en la fecha local de adquisición (Ecuador continental UTC-5; Galápagos UTC-6)."],
    }
    if filtered.empty:
        return result

    work = filtered.copy()
    work["period"] = _period_column(work, granularity)
    grouped = (
        work.groupby(["period", "sensor"], dropna=False)
        .agg(count=("id", "size"), frp_sum=("frp", "sum"), frp_mean=("frp", "mean"), active_days=("acq_date_local", "nunique"))
        .reset_index()
    )
    grouped["frp_sum"] = grouped["frp_sum"].round(2)
    grouped["frp_mean"] = grouped["frp_mean"].round(2)
    grouped = grouped.sort_values(["period", "sensor"])
    result["series"] = grouped.to_dict(orient="records")
    result["totals_by_sensor"] = {str(key): int(value) for key, value in work["sensor"].value_counts().items()}
    return result


def build_calendar(df: pd.DataFrame, spec: FilterSpec, month: str) -> dict:
    try:
        year, month_number = (int(part) for part in month.split("-"))
        start, end = month_bounds(year, month_number)
    except (ValueError, TypeError) as exc:
        raise ValueError("El parámetro month debe tener formato YYYY-MM.") from exc

    month_spec = FilterSpec(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        region_id=spec.region_id,
        sensor=spec.sensor,
        confidence=spec.confidence,
        daynight=spec.daynight,
        min_frp=spec.min_frp,
        bbox=spec.bbox,
    )
    filtered = apply_filters(df, month_spec)
    counts = {}
    if not filtered.empty:
        pivot = filtered.groupby(["acq_date_local", "sensor"]).size().unstack(fill_value=0)
        for day_value, row in pivot.iterrows():
            counts[str(day_value)] = {str(k): int(v) for k, v in row.items()}

    days = []
    max_count = 1
    for offset in range((end - start).days + 1):
        day = start.fromordinal(start.toordinal() + offset)
        day_key = day.isoformat()
        by_sensor = counts.get(day_key, {})
        total = int(sum(by_sensor.values()))
        max_count = max(max_count, total)
        days.append({"date": day_key, "day": day.day, "total": total, "by_sensor": by_sensor, "intensity": 0})

    for day in days:
        if day["total"] > 0:
            day["intensity"] = max(1, min(4, round(day["total"] / max_count * 4 + 0.49)))

    return {
        "month": month,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "max_daily": int(max_count) if days else 0,
        "total": int(sum(day["total"] for day in days)),
        "notes": [
            "La intensidad representa cantidad de detecciones, no superficie quemada.",
            "Los días sin detecciones pueden deberse a ausencia de fuego o a condiciones de observación.",
        ],
    }


def monthly_peaks(df: pd.DataFrame, spec: FilterSpec) -> dict | None:
    filtered = apply_filters(df, spec)
    if filtered.empty:
        return None
    dates = pd.to_datetime(filtered["acq_date_local"], errors="coerce")
    months = dates.dt.strftime("%Y-%m").value_counts()
    days = filtered["acq_date_local"].value_counts()
    return {
        "month": str(months.index[0]),
        "month_count": int(months.iloc[0]),
        "day": str(days.index[0]),
        "day_count": int(days.iloc[0]),
    }
