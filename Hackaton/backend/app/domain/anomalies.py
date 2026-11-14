"""Detección de anomalías diarias con línea base histórica comparable.

Método:
- Se cuenta el número de detecciones por día, región natural y sensor.
- Para cada día del periodo analizado se construye una línea base con los días
  de la misma fecha (± ventana) en años anteriores disponibles.
- Se calcula un z-score robusto respecto a esa línea base y un p-valor normal.
- Se controla el falso descubrimiento con Benjamini-Hochberg (FDR).
- Solo se reportan días con un mínimo de detecciones observadas.

Limitaciones: la ausencia de detección no implica ausencia de fuego; la cobertura
de nubes y la disponibilidad del sensor afectan los conteos. No es un modelo causal.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import pandas as pd

from app.domain.aggregation import region_label
from app.domain.models import FilterSpec, NATURAL_REGIONS
from app.services.data_store import apply_filters


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _p_value(z: float) -> float:
    if math.isinf(z):
        return 0.0
    return math.erfc(abs(z) / math.sqrt(2))


def _bh_qvalues(pvalues: list[float]) -> list[float]:
    """Benjamini-Hochberg: devuelve q-valores en el orden original."""
    n = len(pvalues)
    if n == 0:
        return []
    order = sorted(range(n), key=lambda index: pvalues[index])
    qvalues = [1.0] * n
    previous = 1.0
    for rank in range(n, 0, -1):
        index = order[rank - 1]
        value = min(previous, pvalues[index] * n / rank)
        qvalues[index] = value
        previous = value
    return qvalues


def _analysis_units(df: pd.DataFrame, spec: FilterSpec) -> list[dict]:
    """Define las unidades región+sensor a analizar."""
    if spec.region_id and spec.region_id not in ("all", "ecuador"):
        base = df
        return [
            {
                "region_id": spec.region_id,
                "region": region_label(spec.region_id),
                "sensor": sensor,
                "frame": group,
            }
            for sensor, group in base.groupby("sensor")
        ]

    units = []
    for (region_id, sensor), group in df.groupby(["region_id", "sensor"]):
        if region_id == "outside":
            continue
        units.append(
            {
                "region_id": region_id,
                "region": NATURAL_REGIONS.get(region_id, {}).get("name", region_id),
                "sensor": sensor,
                "frame": group,
            }
        )
    return units


def detect_anomalies(
    df: pd.DataFrame,
    spec: FilterSpec,
    *,
    threshold: float = 2.5,
    window_days: int = 7,
    min_observed: int = 3,
    min_baseline: int = 10,
    fdr_alpha: float = 0.05,
    max_results: int = 40,
) -> dict:
    # Se usa todo el histórico para la línea base, no solo el periodo seleccionado.
    history = apply_filters(df, spec, use_dates=False)
    result = {
        "analysis_period": {"start": spec.start_date, "end": spec.end_date},
        "region": {"id": spec.region_id or "ecuador", "name": region_label(spec.region_id)},
        "sensor_filter": spec.sensor or "all",
        "method": (
            "z-score del conteo diario frente a la media de días comparables "
            f"(misma fecha ±{window_days} días en años anteriores). "
            "p-valor normal bilateral y control FDR Benjamini-Hochberg."
        ),
        "parameters": {
            "z_threshold": threshold,
            "baseline_window_days": window_days,
            "min_observed_detections": min_observed,
            "min_baseline_days": min_baseline,
            "fdr_alpha": fdr_alpha,
            "baseline": "misma fecha ± ventana en años anteriores; se excluye el año del día evaluado",
        },
        "summary": {
            "tests": 0,
            "candidates": 0,
            "flagged": 0,
            "high_anomalies": 0,
            "low_anomalies": 0,
            "regions_affected": [],
            "max_abs_z": None,
        },
        "anomalies": [],
        "notes": [
            "Una anomalía estadística describe un conteo inusual de detecciones, no un incendio confirmado ni su causa.",
            "Los conteos pueden bajar por nubosidad, humo o falta de cobertura del sensor, no solo por menos fuego.",
            "El método usa el histórico disponible; con menos de dos años de línea base los resultados son limitados.",
        ],
    }
    if history.empty:
        result["notes"].append("No hay datos históricos para construir la línea base con los filtros actuales.")
        return result

    history = history.copy()
    history["_date"] = pd.to_datetime(history["acq_date_local"], errors="coerce").dt.date
    history = history.dropna(subset=["_date"])
    if history.empty:
        return result

    units = _analysis_units(history, spec)
    all_tests: list[dict] = []
    analysis_start = date.fromisoformat(spec.start_date)
    analysis_end = date.fromisoformat(spec.end_date)

    for unit in units:
        frame = unit["frame"]
        daily = frame.groupby("_date").size()
        if daily.empty:
            continue
        first_day = min(daily.index)
        last_day = max(daily.index)
        counts = {day: int(value) for day, value in daily.items()}
        years = sorted({day.year for day in counts})
        if len(years) < 2:
            continue

        cursor = max(analysis_start, first_day)
        end_cursor = min(analysis_end, last_day)
        while cursor <= end_cursor:
            baseline_values: list[float] = []
            baseline_dates: list[str] = []
            for year in years:
                if year >= cursor.year:
                    continue
                anchor = _safe_date(year, cursor.month, cursor.day)
                if anchor is None:
                    continue
                for offset in range(-window_days, window_days + 1):
                    candidate = anchor + timedelta(days=offset)
                    if candidate.year == cursor.year:
                        continue
                    if candidate < first_day or candidate > last_day:
                        continue
                    baseline_values.append(float(counts.get(candidate, 0)))
                    if len(baseline_dates) < 15:
                        baseline_dates.append(candidate.isoformat())

            if len(baseline_values) < min_baseline:
                cursor += timedelta(days=1)
                continue

            observed = float(counts.get(cursor, 0))
            mean = sum(baseline_values) / len(baseline_values)
            variance = sum((value - mean) ** 2 for value in baseline_values) / max(1, len(baseline_values) - 1)
            std = math.sqrt(variance)
            if std < 1e-9:
                z = 0.0 if observed == mean else math.copysign(99.0, observed - mean)
            else:
                z = (observed - mean) / std
            p_value = _p_value(z)
            all_tests.append(
                {
                    "date": cursor.isoformat(),
                    "region_id": unit["region_id"],
                    "region": unit["region"],
                    "sensor": unit["sensor"],
                    "observed": int(observed),
                    "baseline_mean": round(mean, 2),
                    "baseline_std": round(std, 2),
                    "baseline_days": len(baseline_values),
                    "baseline_years": sorted({year for year in years if year < cursor.year}),
                    "baseline_dates_sample": baseline_dates,
                    "z_score": round(z, 2) if math.isfinite(z) else z,
                    "p_value": p_value,
                    "direction": "high" if observed > mean else ("low" if observed < mean else "none"),
                }
            )
            cursor += timedelta(days=1)

    if not all_tests:
        result["notes"].append(
            "No hay suficientes años de historia para cada día del periodo (se requieren al menos dos años)."
        )
        return result

    qvalues = _bh_qvalues([item["p_value"] for item in all_tests])
    flagged = []
    for item, qvalue in zip(all_tests, qvalues, strict=True):
        item["q_value"] = qvalue
        passes_z = abs(item["z_score"]) >= threshold
        passes_fdr = qvalue <= fdr_alpha
        passes_min = item["observed"] >= min_observed
        if passes_z and passes_fdr and passes_min:
            item["direction"] = "high" if item["z_score"] > 0 else "low"
            flagged.append(item)

    flagged.sort(key=lambda item: abs(item["z_score"]), reverse=True)
    result["anomalies"] = flagged[:max_results]
    regions = sorted({item["region"] for item in flagged})
    result["summary"] = {
        "tests": len(all_tests),
        "candidates": len(flagged),
        "flagged": len(flagged),
        "high_anomalies": sum(1 for item in flagged if item["direction"] == "high"),
        "low_anomalies": sum(1 for item in flagged if item["direction"] == "low"),
        "regions_affected": regions,
        "max_abs_z": max((abs(item["z_score"]) for item in flagged), default=None),
    }
    if not flagged:
        result["notes"].append(
            "Ningún día superó simultáneamente el umbral de z, el mínimo de detecciones y el control FDR."
        )
    return result
