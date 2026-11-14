"""Capa de acceso al dataset procesado (CSV) y metadatos de procedencia."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.domain.models import FilterSpec
from app.utils.geo import regions_payload

STRING_COLUMNS = [
    "id",
    "source_product",
    "sensor",
    "satellite",
    "instrument",
    "acq_date",
    "acq_time",
    "acquired_at_utc",
    "acq_date_local",
    "acq_time_local",
    "daynight",
    "confidence_raw",
    "confidence_level",
    "version",
    "type",
    "province",
    "province_id",
    "region",
    "region_id",
    "provenance_id",
]

EMPTY_COLUMNS = STRING_COLUMNS + [
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

NUMERIC_COLUMNS = ["latitude", "longitude", "confidence_score", "frp", "brightness", "bright_t31", "bright_ti5", "scan", "track"]


@dataclass
class DatasetMeta:
    mode: str
    path: str | None
    manifest: dict
    loaded_at: str
    rows: int

    @property
    def is_empty(self) -> bool:
        return self.rows == 0


class DataStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._df = pd.DataFrame(columns=EMPTY_COLUMNS)
        self._manifest: dict = {}
        self._mode = "empty"
        self._path: Path | None = None
        self._mtime: float | None = None
        self._loaded_at = ""
        self._evidence_df: pd.DataFrame | None = None
        self._evidence_mtime: float | None = None
        self.refresh(force=True)

    # ------------------------------------------------------------------ loading
    def _resolve_source(self) -> tuple[Path | None, Path | None, str]:
        settings = get_settings()
        if settings.detections_file.exists() and settings.detections_file.stat().st_size > 0:
            return settings.detections_file, settings.manifest_file, "real"
        sample = settings.samples_dir / "detections_sample.csv"
        if sample.exists() and sample.stat().st_size > 0:
            return sample, settings.samples_dir / "manifest.json", "sample"
        return None, None, "empty"

    def refresh(self, force: bool = False) -> None:
        path, manifest_path, mode = self._resolve_source()
        mtime = path.stat().st_mtime if path else None
        with self._lock:
            if not force and mtime == self._mtime and mode == self._mode:
                return
            if path is None:
                self._df = pd.DataFrame(columns=EMPTY_COLUMNS)
                self._manifest = {}
                self._mode = "empty"
                self._path = None
                self._mtime = None
                self._evidence_df = None
                self._evidence_mtime = None
                self._loaded_at = pd.Timestamp.now(tz="UTC").isoformat()
                return
            frame = pd.read_csv(path, dtype={column: "string" for column in STRING_COLUMNS}, low_memory=False)
            for column in NUMERIC_COLUMNS:
                if column in frame:
                    frame[column] = pd.to_numeric(frame[column], errors="coerce")
            for column in ["acq_time", "acq_time_local"]:
                if column in frame:
                    frame[column] = frame[column].fillna("").astype(str).str.zfill(4 if column == "acq_time" else 5)
            if "acq_date_local" not in frame and "acq_date" in frame:
                frame["acq_date_local"] = frame["acq_date"]
            self._df = frame
            self._mode = mode
            self._path = path
            self._mtime = mtime
            self._evidence_df = None
            self._evidence_mtime = None
            self._loaded_at = pd.Timestamp.now(tz="UTC").isoformat()
            self._manifest = {}
            if manifest_path and manifest_path.exists():
                with manifest_path.open(encoding="utf-8") as handle:
                    self._manifest = json.load(handle)

    # ------------------------------------------------------------------ access
    @property
    def df(self) -> pd.DataFrame:
        self.refresh()
        return self._df

    @property
    def evidence_df(self) -> pd.DataFrame:
        """Dataset con columnas derivadas de evidencia de incendio (cacheado)."""
        self.refresh()
        with self._lock:
            if self._evidence_df is None or self._evidence_mtime != self._mtime:
                from app.domain.fire_evidence import annotate_fire_evidence

                self._evidence_df = annotate_fire_evidence(self._df)
                self._evidence_mtime = self._mtime
            return self._evidence_df

    @property
    def manifest(self) -> dict:
        self.refresh()
        return self._manifest

    @property
    def mode(self) -> str:
        self.refresh()
        return self._mode

    @property
    def meta(self) -> DatasetMeta:
        self.refresh()
        return DatasetMeta(
            mode=self._mode,
            path=str(self._path) if self._path else None,
            manifest=self._manifest,
            loaded_at=self._loaded_at,
            rows=len(self._df),
        )

    def date_bounds(self) -> tuple[str | None, str | None]:
        df = self.df
        if df.empty:
            return None, None
        return str(df["acq_date_local"].min()), str(df["acq_date_local"].max())

    def default_window(self, days: int = 365) -> tuple[str, str]:
        start, end = self.date_bounds()
        if not start or not end:
            today = date.today()
            return (today - timedelta(days=days)).isoformat(), today.isoformat()
        end_date = date.fromisoformat(end)
        start_date = max(date.fromisoformat(start), end_date - timedelta(days=days - 1))
        return start_date.isoformat(), end_date.isoformat()

    def meta_payload(self) -> dict:
        df = self.df
        meta = self.meta
        start, end = self.date_bounds()
        default_start, default_end = self.default_window()
        by_sensor = df["sensor"].value_counts().to_dict() if not df.empty else {}
        date_by_sensor = {}
        if not df.empty:
            for sensor, group in df.groupby("sensor"):
                date_by_sensor[sensor] = {
                    "start": str(group["acq_date_local"].min()),
                    "end": str(group["acq_date_local"].max()),
                    "count": int(len(group)),
                }
        regions = regions_payload()
        return {
            "app": "FuegoClaro",
            "version": get_settings().version,
            "data_mode": meta.mode,
            "dataset_version": meta.manifest.get("dataset_version"),
            "generated_at": meta.manifest.get("generated_at"),
            "date_range": {"start": start, "end": end},
            "default_window": {"start": default_start, "end": default_end},
            "by_sensor": by_sensor,
            "date_by_sensor": date_by_sensor,
            "sensors": [
                {"id": "MODIS", "name": "MODIS", "description": "Terra/Aqua · ~1 km · confianza 0–100"},
                {"id": "VIIRS", "name": "VIIRS", "description": "NOAA-20 · ~375 m · confianza low/nominal/high"},
            ],
            "products": sorted(df["source_product"].dropna().unique().tolist()) if not df.empty else [],
            "confidence_levels": ["low", "nominal", "high", "unknown"],
            "regions": regions["regions"],
            "provinces": regions["provinces"],
            "attribution": meta.manifest.get("attribution"),
            "source": meta.manifest.get("source"),
            "limitations": meta.manifest.get("limitations", []),
            "warnings": meta.manifest.get("warnings", []),
            "records": meta.manifest.get("records", {}),
        }


_store = DataStore()


def get_store() -> DataStore:
    return _store


def apply_filters(df: pd.DataFrame, spec: FilterSpec, *, use_dates: bool = True) -> pd.DataFrame:
    if df.empty:
        return df
    out = df
    if use_dates:
        out = out[(out["acq_date_local"] >= spec.start_date) & (out["acq_date_local"] <= spec.end_date)]
    if spec.region_id and spec.region_id not in ("all", "ecuador"):
        out = out[(out["region_id"] == spec.region_id) | (out["province_id"] == spec.region_id)]
    if spec.sensor and spec.sensor != "all":
        out = out[out["sensor"] == spec.sensor]
    if spec.confidence:
        out = out[out["confidence_level"].isin(spec.confidence)]
    if spec.daynight and spec.daynight in ("D", "N"):
        out = out[out["daynight"] == spec.daynight]
    if spec.min_frp is not None:
        out = out[out["frp"].fillna(0) >= spec.min_frp]
    if spec.bbox:
        west, south, east, north = spec.bbox
        out = out[
            out["longitude"].between(west, east)
            & out["latitude"].between(south, north)
        ]
    return out
