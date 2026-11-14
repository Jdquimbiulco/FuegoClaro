"""Capa de evidencia de incendio y contexto de fuentes térmicas.

Una detección de foco de calor de NASA FIRMS no es un incendio confirmado. Este
módulo no intenta "confirmar" incendios: construye un **índice de evidencia**
transparente y reproducible para separar detecciones con señal fuerte de
detecciones débiles o compatibles con fuentes no asociadas a biomasa.

El índice combina, con reglas explícitas y sin aprendizaje supervisado:

- confianza normalizada del producto (MODIS 0-100; VIIRS low/nominal/high),
- FRP (energía radiativa) cuando existe,
- contraste térmico brillo - temperatura de fondo (canal 31 MODIS / 5 VIIRS),
- detección nocturna,
- corroboración espacial entre MODIS y VIIRS el mismo día,
- soporte de un grupo espacial denso de detecciones.

Además agrega un ``context_flag`` por celda para señalar fuentes térmicas
persistentes que requieren revisión (posible actividad volcánica/geotérmica o
quema industrial). Es una señal de contexto, no una clasificación definitiva.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

EVIDENCE_LEVELS = ("high", "moderate", "low")
EVIDENCE_HIGH_THRESHOLD = 70.0
EVIDENCE_MODERATE_THRESHOLD = 45.0

# Valor de confianza usado para el componente de confianza. Para MODIS se usa
# el score 0-100 cuando existe; para VIIRS no se inventa un score numérico, se
# mapea su categoría a un valor de trabajo interno.
_CONFIDENCE_VALUE = {
    "low": 20.0,
    "nominal": 60.0,
    "high": 90.0,
    "unknown": 30.0,
}

_CONTEXT_LABELS = {
    "none": "Sin contexto persistente",
    "persistent_heat_source": "Fuente térmica persistente (revisar)",
    "possible_volcanic_or_geothermal": "Posible fuente volcánica/geotérmica",
    "possible_industrial_flare": "Posible quema industrial (gas/vapor)",
    "seasonal_burning": "Patrón estacional compatible con quema de biomasa",
}

# Provincias amazónicas con actividad petrolera conocida. Solo se usa como
# contexto heurístico para señalar detecciones persistentes que requieren
# revisión; no afirma que una detección sea un mechero industrial.
_OIL_PROVINCES = {"sucumbios", "orellana"}


def _series(df: pd.DataFrame, column: str, default: float | str | None = None) -> pd.Series:
    if column in df.columns:
        return df[column]
    return pd.Series([default] * len(df), index=df.index)


def _numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _confidence_values(df: pd.DataFrame) -> pd.Series:
    sensor = _series(df, "sensor", "").astype(str)
    level = _series(df, "confidence_level", "unknown").astype(str).str.lower()
    mapped = level.map(_CONFIDENCE_VALUE).fillna(_CONFIDENCE_VALUE["unknown"])
    score = _numeric(df, "confidence_score")
    # MODIS conserva su score 0-100; VIIRS usa la categoría mapeada.
    modis_with_score = sensor.eq("MODIS") & score.notna()
    values = mapped.astype(float)
    values.loc[modis_with_score] = score.loc[modis_with_score].clip(0, 100)
    return values


def _thermal_contrast(df: pd.DataFrame) -> pd.Series:
    sensor = _series(df, "sensor", "").astype(str)
    brightness = _numeric(df, "brightness")
    t31 = _numeric(df, "bright_t31")
    ti5 = _numeric(df, "bright_ti5")
    contrast = np.where(sensor.eq("MODIS"), brightness - t31, brightness - ti5)
    return pd.Series(np.maximum(contrast, 0), index=df.index, dtype=float).fillna(0.0)


def _cell_keys(df: pd.DataFrame, cell_degrees: float) -> pd.DataFrame:
    lat = _numeric(df, "latitude").fillna(0.0).to_numpy()
    lon = _numeric(df, "longitude").fillna(0.0).to_numpy()
    return pd.DataFrame(
        {
            "row": np.arange(len(df)),
            "sensor": _series(df, "sensor", "").astype(str).to_numpy(),
            "date": _series(df, "acq_date_local", "").astype(str).to_numpy(),
            "lat_cell": np.floor(lat / cell_degrees).astype("int64"),
            "lon_cell": np.floor(lon / cell_degrees).astype("int64"),
        }
    )


def _spatial_support(df: pd.DataFrame, cell_degrees: float) -> tuple[pd.Series, pd.Series]:
    """Devuelve (corroboración entre sensores, conteo de vecinos).

    Se usa una rejilla de ``cell_degrees`` y una vecindad de 3x3 celdas. La
    corroboración entre sensores exige el mismo día local; no se inventan
    correspondencias temporales.
    """
    keys = _cell_keys(df, cell_degrees)
    if keys.empty:
        return (
            pd.Series(False, index=df.index, dtype=bool),
            pd.Series(0, index=df.index, dtype=int),
        )

    counts = (
        keys.groupby(["sensor", "date", "lat_cell", "lon_cell"], sort=False)
        .size()
        .rename("n")
        .reset_index()
    )
    other_counts = counts.copy()
    other_counts["sensor"] = other_counts["sensor"].map({"MODIS": "VIIRS", "VIIRS": "MODIS"})

    neighbours = pd.Series(0, index=range(len(df)), dtype=int)
    cross = pd.Series(False, index=range(len(df)), dtype=bool)

    for delta_lat in (-1, 0, 1):
        for delta_lon in (-1, 0, 1):
            probe = keys.copy()
            probe["lat_cell"] += delta_lat
            probe["lon_cell"] += delta_lon

            merged = probe.merge(
                counts,
                on=["sensor", "date", "lat_cell", "lon_cell"],
                how="left",
            )
            neighbours = neighbours.add(
                merged.set_index("row")["n"].fillna(0).astype(int),
                fill_value=0,
            )

            cross_merged = probe.merge(
                other_counts,
                on=["sensor", "date", "lat_cell", "lon_cell"],
                how="inner",
            )
            if not cross_merged.empty:
                cross.loc[cross_merged["row"].unique()] = True

    neighbours.index = df.index
    cross.index = df.index
    return cross, neighbours


def _cell_context(df: pd.DataFrame, cell_degrees: float) -> pd.DataFrame:
    """Estadísticos de recurrencia por celda para señalar fuentes persistentes."""
    keys = _cell_keys(df, cell_degrees)
    dates = pd.to_datetime(_series(df, "acq_date_local", "").astype(str), errors="coerce")
    keys["year"] = dates.dt.year.to_numpy()
    keys["month"] = dates.dt.month.to_numpy()
    keys["day"] = _series(df, "acq_date_local", "").astype(str).to_numpy()

    grouped = keys.groupby(["lat_cell", "lon_cell"], sort=False).agg(
        cell_total=("row", "size"),
        cell_years=("year", "nunique"),
        cell_months=("month", "nunique"),
        cell_days=("day", "nunique"),
    )
    metrics = keys.merge(grouped.reset_index(), on=["lat_cell", "lon_cell"], how="left")

    province = _series(df, "province_id", "").astype(str).str.lower().to_numpy()
    region = _series(df, "region_id", "").astype(str).str.lower().to_numpy()

    context = np.full(len(df), "none", dtype=object)
    persistent = (
        (metrics["cell_years"].to_numpy() >= 3)
        & (metrics["cell_months"].to_numpy() >= 10)
        & (metrics["cell_days"].to_numpy() >= 20)
    )
    seasonal = (
        (metrics["cell_years"].to_numpy() >= 2)
        & (metrics["cell_months"].to_numpy() <= 5)
        & (metrics["cell_days"].to_numpy() >= 10)
    )
    context[persistent & (region == "galapagos")] = "possible_volcanic_or_geothermal"
    context[persistent & (region != "galapagos") & np.isin(province, list(_OIL_PROVINCES))] = "possible_industrial_flare"
    context[persistent & (context == "none")] = "persistent_heat_source"
    context[~persistent & seasonal] = "seasonal_burning"

    return pd.DataFrame(
        {
            "row": np.arange(len(df)),
            "cell_years": metrics["cell_years"].to_numpy(),
            "cell_months": metrics["cell_months"].to_numpy(),
            "cell_days": metrics["cell_days"].to_numpy(),
            "cell_total": metrics["cell_total"].to_numpy(),
            "context_flag": context,
        }
    )


def _reason_text(row: dict) -> str:
    reasons: list[str] = []
    level = row["confidence_level"]
    if level == "high":
        reasons.append("confianza alta")
    elif level == "nominal":
        reasons.append("confianza nominal")
    elif level == "low":
        reasons.append("confianza baja")
    else:
        reasons.append("confianza desconocida")

    frp = row["frp"]
    if pd.notna(frp) and frp >= 20:
        reasons.append("FRP alto")
    elif pd.notna(frp) and frp >= 5:
        reasons.append("FRP medio")

    delta = row["thermal_contrast"]
    if pd.notna(delta) and delta >= 40:
        reasons.append("contraste térmico alto")
    elif pd.notna(delta) and delta >= 20:
        reasons.append("contraste térmico medio")

    if row["daynight"] == "N":
        reasons.append("detección nocturna")
    if row["cross_sensor"]:
        reasons.append("corroboración MODIS/VIIRS")
    if row["neighbour_count"] >= 3:
        reasons.append("grupo espacial denso")
    if row["context_flag"] != "none":
        reasons.append(_CONTEXT_LABELS.get(row["context_flag"], row["context_flag"]))
    return " | ".join(reasons)


def annotate_fire_evidence(
    df: pd.DataFrame,
    *,
    cell_degrees: float = 0.01,
) -> pd.DataFrame:
    """Añade columnas de evidencia y contexto sin modificar los datos originales.

    Columnas añadidas:
    - ``evidence_score``: 0-100 (índice, no probabilidad).
    - ``evidence_level``: ``high``/``moderate``/``low``.
    - ``evidence_reasons``: texto auditable con las señales usadas.
    - ``context_flag``: contexto heurístico por celda recurrente.
    - ``evidence_cell_years`` / ``evidence_cell_months``: recurrencia de la celda.
    - ``evidence_neighbours``: detecciones en la vecindad 3x3 del mismo sensor/día.
    - ``evidence_cross_sensor``: si hay otro sensor en la vecindad el mismo día.
    """
    if df.empty:
        out = df.copy()
        out["evidence_score"] = pd.Series(dtype=float)
        out["evidence_level"] = pd.Series(dtype="object")
        out["evidence_reasons"] = pd.Series(dtype="object")
        out["context_flag"] = pd.Series(dtype="object")
        out["evidence_cell_years"] = pd.Series(dtype="int64")
        out["evidence_cell_months"] = pd.Series(dtype="int64")
        out["evidence_neighbours"] = pd.Series(dtype="int64")
        out["evidence_cross_sensor"] = pd.Series(dtype=bool)
        return out

    work = df.copy()
    sensor = _series(work, "sensor", "").astype(str)
    level = _series(work, "confidence_level", "unknown").astype(str).str.lower()
    frp = _numeric(work, "frp").fillna(0.0)
    contrast = _thermal_contrast(work)
    daynight = _series(work, "daynight", "").astype(str).str.upper()

    confidence_value = _confidence_values(work)
    cross, neighbours = _spatial_support(work, cell_degrees)
    cell_context = _cell_context(work, cell_degrees)

    # Componentes con pesos explícitos (máximo teórico 103; se recorta a 100).
    confidence_component = confidence_value * 0.45
    frp_component = np.minimum(20.0, np.log1p(frp.clip(lower=0)) / math.log1p(100.0) * 20.0)
    thermal_component = np.minimum(20.0, np.maximum(0.0, (contrast - 10.0) / 50.0 * 20.0))
    night_component = np.where(daynight == "N", 5.0, 0.0)
    cross_component = np.where(cross.to_numpy(), 8.0, 0.0)
    cluster_component = np.where(neighbours.to_numpy() >= 3, 5.0, 0.0)
    penalty = np.where(level == "low", -8.0, np.where(level == "unknown", -4.0, 0.0))

    score = (
        confidence_component.to_numpy()
        + frp_component
        + thermal_component
        + night_component
        + cross_component
        + cluster_component
        + penalty
    )
    score = np.clip(np.round(score), 0, 100)

    work["evidence_score"] = score
    work["evidence_level"] = np.select(
        [score >= EVIDENCE_HIGH_THRESHOLD, score >= EVIDENCE_MODERATE_THRESHOLD],
        ["high", "moderate"],
        default="low",
    )
    work["context_flag"] = cell_context["context_flag"].to_numpy()
    work["evidence_cell_years"] = cell_context["cell_years"].fillna(0).astype(int).to_numpy()
    work["evidence_cell_months"] = cell_context["cell_months"].fillna(0).astype(int).to_numpy()
    work["evidence_neighbours"] = neighbours.to_numpy()
    work["evidence_cross_sensor"] = cross.to_numpy()

    reason_frame = pd.DataFrame(
        {
            "confidence_level": level.to_numpy(),
            "frp": frp.to_numpy(),
            "thermal_contrast": contrast.to_numpy(),
            "daynight": daynight.to_numpy(),
            "cross_sensor": cross.to_numpy(),
            "neighbour_count": neighbours.to_numpy(),
            "context_flag": work["context_flag"].to_numpy(),
        }
    )
    work["evidence_reasons"] = [_reason_text(row) for row in reason_frame.to_dict(orient="records")]
    return work


def summarise_evidence(df: pd.DataFrame, spec=None) -> dict:
    """Resumen agregado de evidencia para el periodo/región filtrados."""
    from app.services.data_store import apply_filters

    annotated = df if "evidence_level" in df.columns else annotate_fire_evidence(df)
    filtered = apply_filters(annotated, spec) if spec is not None else annotated
    total = int(len(filtered))
    result = {
        "total": total,
        "mean_score": None,
        "median_score": None,
        "by_level": {"high": 0, "moderate": 0, "low": 0},
        "by_sensor": [],
        "by_region": [],
        "by_context": [],
        "top_reasons": [],
        "notes": [
            "El índice de evidencia es una regla transparente, no una probabilidad ni una confirmación de incendio.",
            "Las fuentes térmicas persistentes pueden ser volcánicas o industriales; el contexto solo señala dónde revisar.",
        ],
        "method": (
            "Índice 0-100 con confianza (45%), FRP (20%), contraste térmico (20%), "
            "noche (5%), corroboración MODIS/VIIRS (8%) y grupo espacial (5%), con penalización por confianza baja."
        ),
    }
    if filtered.empty:
        return result

    scores = pd.to_numeric(filtered["evidence_score"], errors="coerce")
    result["mean_score"] = round(float(scores.mean()), 2)
    result["median_score"] = round(float(scores.median()), 2)

    level_counts = filtered["evidence_level"].value_counts()
    result["by_level"] = {
        level: int(level_counts.get(level, 0)) for level in EVIDENCE_LEVELS
    }

    for sensor, group in filtered.groupby("sensor"):
        counts = group["evidence_level"].value_counts()
        result["by_sensor"].append(
            {
                "sensor": str(sensor),
                "total": int(len(group)),
                "high": int(counts.get("high", 0)),
                "moderate": int(counts.get("moderate", 0)),
                "low": int(counts.get("low", 0)),
                "mean_score": round(float(pd.to_numeric(group["evidence_score"], errors="coerce").mean()), 2),
            }
        )
    result["by_sensor"].sort(key=lambda item: item["total"], reverse=True)

    for region_id, group in filtered.groupby("region_id"):
        counts = group["evidence_level"].value_counts()
        result["by_region"].append(
            {
                "region_id": str(region_id),
                "region": str(group["region"].iloc[0]) if "region" in group and not group.empty else str(region_id),
                "total": int(len(group)),
                "high": int(counts.get("high", 0)),
                "low": int(counts.get("low", 0)),
            }
        )
    result["by_region"].sort(key=lambda item: item["total"], reverse=True)

    for flag, group in filtered.groupby("context_flag"):
        result["by_context"].append(
            {
                "context_flag": str(flag),
                "label": _CONTEXT_LABELS.get(str(flag), str(flag)),
                "total": int(len(group)),
                "high": int((group["evidence_level"] == "high").sum()),
            }
        )
    result["by_context"].sort(key=lambda item: item["total"], reverse=True)

    reason_counts: dict[str, int] = {}
    for value in filtered["evidence_reasons"].fillna(""):
        for reason in str(value).split(" | "):
            reason = reason.strip()
            if reason:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
    result["top_reasons"] = [
        {"reason": reason, "count": count}
        for reason, count in sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)[:8]
    ]
    return result
