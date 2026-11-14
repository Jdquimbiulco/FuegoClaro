"""Normalización de registros NASA FIRMS al modelo canónico de FuegoClaro."""

from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from app.domain.models import ConfidenceLevel, Sensor

CANONICAL_COLUMNS = [
    "id",
    "source_product",
    "sensor",
    "satellite",
    "instrument",
    "latitude",
    "longitude",
    "acq_date",
    "acq_time",
    "acquired_at_utc",
    "acq_date_local",
    "acq_time_local",
    "daynight",
    "confidence_raw",
    "confidence_level",
    "confidence_score",
    "frp",
    "brightness",
    "bright_t31",
    "bright_ti5",
    "scan",
    "track",
    "version",
    "type",
    "province",
    "province_id",
    "region",
    "region_id",
    "provenance_id",
]

NUMERIC_COLUMNS = [
    "latitude",
    "longitude",
    "confidence_score",
    "frp",
    "brightness",
    "bright_t31",
    "bright_ti5",
    "scan",
    "track",
]

SATELLITE_NAMES = {
    "T": "Terra",
    "A": "Aqua",
    "TERRA": "Terra",
    "AQUA": "Aqua",
    "N": "Suomi-NPP",
    "NPP": "Suomi-NPP",
    "SNPP": "Suomi-NPP",
    "N20": "NOAA-20",
    "N21": "NOAA-21",
    "NOAA-20": "NOAA-20",
    "NOAA-21": "NOAA-21",
}


def classify_confidence(raw: object, sensor: str) -> tuple[str, float | None]:
    """Devuelve (nivel_normalizado, score_numerico).

    MODIS: 0-100 -> low <30, nominal 30-79, high >=80 (criterio FIRMS).
    VIIRS: categoría low/nominal/high. No se inventa un score numérico.
    """
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return ConfidenceLevel.UNKNOWN.value, None

    text = str(raw).strip().lower()
    if sensor == Sensor.MODIS:
        try:
            score = float(text)
        except ValueError:
            mapping = {"l": ConfidenceLevel.LOW, "low": ConfidenceLevel.LOW,
                       "n": ConfidenceLevel.NOMINAL, "nominal": ConfidenceLevel.NOMINAL,
                       "h": ConfidenceLevel.HIGH, "high": ConfidenceLevel.HIGH}
            level = mapping.get(text, ConfidenceLevel.UNKNOWN)
            return level.value, None
        if score < 30:
            level = ConfidenceLevel.LOW
        elif score < 80:
            level = ConfidenceLevel.NOMINAL
        else:
            level = ConfidenceLevel.HIGH
        return level.value, score

    mapping = {"l": ConfidenceLevel.LOW, "low": ConfidenceLevel.LOW,
               "n": ConfidenceLevel.NOMINAL, "nominal": ConfidenceLevel.NOMINAL,
               "h": ConfidenceLevel.HIGH, "high": ConfidenceLevel.HIGH}
    return mapping.get(text, ConfidenceLevel.UNKNOWN).value, None


def _normalize_satellite(value: object) -> str:
    text = str(value or "").strip()
    return SATELLITE_NAMES.get(text.upper(), text or "Desconocido")


def normalize_chunk(
    df: pd.DataFrame,
    *,
    source_product: str,
    sensor: str,
    provenance_id: str,
) -> pd.DataFrame:
    """Convierte un CSV crudo de FIRMS en registros canónicos.

    Conserva los campos originales relevantes (brightness/bright_ti4, bright_t31/bright_ti5,
    confianza original, versión, scan/track) y agrega campos derivados.
    """
    if df.empty:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    out = pd.DataFrame(index=df.index)

    out["source_product"] = source_product
    out["sensor"] = sensor
    out["satellite"] = df.get("satellite", pd.Series(index=df.index, dtype="object")).map(_normalize_satellite)
    out["instrument"] = df.get("instrument", pd.Series("", index=df.index)).astype(str)
    out["latitude"] = pd.to_numeric(df.get("latitude"), errors="coerce")
    out["longitude"] = pd.to_numeric(df.get("longitude"), errors="coerce")
    out["acq_date"] = df.get("acq_date", pd.Series(index=df.index)).astype(str)
    out["acq_time"] = (
        df.get("acq_time", pd.Series(index=df.index)).astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    )
    out["daynight"] = df.get("daynight", pd.Series(index=df.index)).astype(str).str.upper().str[:1]

    # Campos de brillo: MODIS usa brightness/bright_t31; VIIRS bright_ti4/bright_ti5.
    out["brightness"] = pd.to_numeric(
        df["brightness"] if "brightness" in df else df.get("bright_ti4"), errors="coerce"
    )
    out["bright_t31"] = pd.to_numeric(df.get("bright_t31"), errors="coerce")
    out["bright_ti5"] = pd.to_numeric(df.get("bright_ti5"), errors="coerce")
    out["frp"] = pd.to_numeric(df.get("frp"), errors="coerce")
    out["scan"] = pd.to_numeric(df.get("scan"), errors="coerce")
    out["track"] = pd.to_numeric(df.get("track"), errors="coerce")
    out["version"] = df.get("version", pd.Series(index=df.index)).astype(str)
    out["type"] = df.get("type", pd.Series(index=df.index)).astype(str)

    raw_confidence = df.get("confidence", pd.Series(index=df.index))
    out["confidence_raw"] = raw_confidence.astype(str)
    classified = raw_confidence.map(lambda value: classify_confidence(value, sensor))
    out["confidence_level"] = [item[0] for item in classified]
    out["confidence_score"] = [item[1] for item in classified]

    out["acquired_at_utc"] = pd.to_datetime(
        out["acq_date"].str.strip() + " " + out["acq_time"],
        format="%Y-%m-%d %H%M",
        utc=True,
        errors="coerce",
    ).astype("string")
    out["acq_date_local"] = pd.Series(index=df.index, dtype="object")
    out["acq_time_local"] = pd.Series(index=df.index, dtype="object")

    out["province"] = pd.Series(index=df.index, dtype="object")
    out["province_id"] = pd.Series(index=df.index, dtype="object")
    out["region"] = pd.Series(index=df.index, dtype="object")
    out["region_id"] = pd.Series(index=df.index, dtype="object")

    out["provenance_id"] = provenance_id

    # ID determinista: misma detección -> mismo id (permite deduplicar reintentos).
    fingerprint = (
        out["source_product"].astype(str)
        + "|"
        + out["satellite"].astype(str)
        + "|"
        + out["acq_date"].astype(str)
        + "|"
        + out["acq_time"].astype(str)
        + "|"
        + out["latitude"].round(6).astype(str)
        + "|"
        + out["longitude"].round(6).astype(str)
    )
    out["id"] = fingerprint.map(lambda value: hashlib.sha1(value.encode("utf-8")).hexdigest()[:20])

    for column in NUMERIC_COLUMNS:
        if column in out:
            out[column] = pd.to_numeric(out[column], errors="coerce")

    return out[CANONICAL_COLUMNS]


def add_local_time(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega fecha/hora local de Ecuador.

    Ecuador continental usa UTC-5; Galápagos UTC-6. Se usa el huso correspondiente
    a la región ya asignada. La fecha local es la base de calendario y series diarias.
    """
    if df.empty:
        return df
    out = df.copy()
    offset_hours = np.where(out["region_id"].eq("galapagos"), -6, -5)
    utc = pd.to_datetime(out["acquired_at_utc"], utc=True, errors="coerce")
    local = utc + pd.to_timedelta(offset_hours, unit="h")
    out["acq_date_local"] = local.dt.strftime("%Y-%m-%d")
    out["acq_time_local"] = local.dt.strftime("%H:%M")
    return out
