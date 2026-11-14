"""Validación y limpieza de registros de focos de calor."""

from __future__ import annotations

import pandas as pd

REQUIRED_FIELDS = ["latitude", "longitude", "acq_date", "acq_time", "sensor", "confidence_level"]


def validate_detections(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Aplica reglas mínimas de calidad y devuelve (df_limpio, reporte).

    No corrige coordenadas ni fechas: descarta registros inválidos y los cuenta.
    """
    report: dict[str, int] = {"input": int(len(df))}
    if df.empty:
        report.update({"valid": 0, "dropped_missing_fields": 0, "dropped_invalid_coords": 0, "dropped_invalid_datetime": 0, "dropped_duplicates": 0})
        return df, report

    missing_columns = [column for column in REQUIRED_FIELDS if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Faltan campos obligatorios: {', '.join(missing_columns)}")

    work = df.copy()
    missing = work[REQUIRED_FIELDS].isna().any(axis=1)
    report["dropped_missing_fields"] = int(missing.sum())
    work = work[~missing]

    valid_coords = (
        work["latitude"].between(-90, 90)
        & work["longitude"].between(-180, 180)
        & ~((work["latitude"] == 0) & (work["longitude"] == 0))
    )
    report["dropped_invalid_coords"] = int((~valid_coords).sum())
    work = work[valid_coords]

    valid_datetime = pd.to_datetime(work["acquired_at_utc"], utc=True, errors="coerce").notna()
    report["dropped_invalid_datetime"] = int((~valid_datetime).sum())
    work = work[valid_datetime]

    before_dedup = len(work)
    work = work.drop_duplicates(subset=["id"], keep="first")
    report["dropped_duplicates"] = int(before_dedup - len(work))
    report["valid"] = int(len(work))
    return work.reset_index(drop=True), report
