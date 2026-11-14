"""Orquestación de ingesta: FIRMS -> normalización -> validación -> dataset procesado."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.domain.models import ECUADOR_BBOX, SOURCE_PLAN
from app.domain.normalization import CANONICAL_COLUMNS, add_local_time, normalize_chunk
from app.domain.validation import validate_detections
from app.services.firms_client import FirmsClient
from app.utils.geo import assign_provinces

logger = logging.getLogger(__name__)


def _sensor_for_product(product: str) -> str:
    return "MODIS" if product.startswith("MODIS") else "VIIRS"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_path(path: Path) -> Path:
    """Crea un archivo temporal en el mismo directorio para reemplazo atómico."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    os.close(descriptor)
    return Path(temp_name)


def _write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    temp_path = _atomic_path(path)
    try:
        frame.to_csv(temp_path, index=False, float_format="%.6f")
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _write_manifest(path: Path, payload: dict) -> None:
    temp_path = _atomic_path(path)
    try:
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _build_sample(detections: pd.DataFrame, max_rows: int = 12000, days: int = 120) -> pd.DataFrame:
    """Muestra auténtica reciente para demo offline. Nunca se etiqueta como otra cosa."""
    if detections.empty:
        return detections
    max_date = pd.to_datetime(detections["acq_date_local"]).max()
    cutoff = (max_date - pd.Timedelta(days=days)).date().isoformat()
    recent = detections[detections["acq_date_local"] >= cutoff]
    if recent.empty:
        recent = detections
    parts = []
    for sensor, group in recent.groupby("sensor"):
        parts.append(group.sort_values("acquired_at_utc", ascending=False).head(max_rows // 2))
    sample = pd.concat(parts, ignore_index=True) if parts else recent
    return sample.sort_values("acquired_at_utc", ascending=False).head(max_rows)


def ingest(
    start: date,
    end: date,
    *,
    bbox: tuple[float, float, float, float] = ECUADOR_BBOX,
    keep_raw: bool = False,
    make_sample: bool = True,
) -> dict:
    settings = get_settings()
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.manifests_dir.mkdir(parents=True, exist_ok=True)
    settings.samples_dir.mkdir(parents=True, exist_ok=True)

    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client = FirmsClient()
    if not client.configured:
        raise RuntimeError("FIRMS_MAP_KEY no configurada. Copia backend/.env.example a backend/.env y agrega tu clave.")

    try:
        availability = client.availability()
        segments = client.plan_segments(start, end, availability)
        if not segments:
            raise RuntimeError("No hay datos FIRMS disponibles para el periodo solicitado.")
        logger.info(
            "Ingesta %s..%s | %s tramos: %s",
            start,
            end,
            len(segments),
            ", ".join(f"{s.source_product} {s.start}..{s.end}" for s in segments),
        )
        results, source_report = client.fetch_all(start, end, bbox=bbox, availability=availability)
    finally:
        client.close()

    raw_frames: list[pd.DataFrame] = []
    normalized_parts: list[pd.DataFrame] = []
    raw_records = 0
    for product, frame in results:
        raw_records += len(frame)
        if frame.empty:
            continue
        sensor = _sensor_for_product(product)
        normalized_parts.append(
            normalize_chunk(frame, source_product=product, sensor=sensor, provenance_id=run_id)
        )
        if keep_raw:
            raw_path = settings.data_dir / "raw" / f"{product}_{start.isoformat()}_{end.isoformat()}.csv"
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            frame.to_csv(raw_path, index=False)
            raw_frames.append(frame)

    if not normalized_parts:
        raise RuntimeError(
            "FIRMS no devolvió registros para el periodo. Revisa la disponibilidad de productos o el bbox."
        )

    detections = pd.concat(normalized_parts, ignore_index=True)
    normalized_count = int(len(detections))

    # Asignación espacial (solo puntos dentro de Ecuador) y hora local.
    detections = assign_provinces(detections)
    outside = int((detections["region_id"] == "outside").sum())
    detections = detections[detections["region_id"] != "outside"].copy()
    detections = add_local_time(detections)
    detections, validation_report = validate_detections(detections)

    detections = detections.sort_values(["acquired_at_utc", "sensor"], ascending=[False, True]).reset_index(drop=True)

    output = settings.detections_file
    _write_csv_atomic(detections, output)
    file_hash = _sha256(output)

    by_sensor = detections["sensor"].value_counts().to_dict()
    by_product = detections["source_product"].value_counts().to_dict()
    by_confidence = detections["confidence_level"].value_counts().to_dict()
    by_region = detections["region_id"].value_counts().to_dict()

    manifest = {
        "dataset_version": f"fuegoclaro-{run_id}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "data_mode": "real",
        "source": "NASA FIRMS – Fire Information for Resource Management System",
        "source_url": "https://firms.modaps.eosdis.nasa.gov/",
        "attribution": "NASA FIRMS (MODIS Collection 6.1 y VIIRS 375 m). Datos procesados por FuegoClaro.",
        "requested_period": {"start": start.isoformat(), "end": end.isoformat()},
        "bbox": list(bbox),
        "sources": [
            {
                **item,
                "sensor": _sensor_for_product(item["source_product"]),
                "label": next(
                    (p["label"] for p in SOURCE_PLAN if item["source_product"] in (p["sp"], p["nrt"])),
                    item["source_product"],
                ),
            }
            for item in source_report
        ],
        "availability": {key: {"min": value[0].isoformat(), "max": value[1].isoformat()} for key, value in availability.items()},
        "records": {
            "raw_downloaded": raw_records,
            "normalized": normalized_count,
            "excluded_outside_ecuador": outside,
            **validation_report,
            "final": int(len(detections)),
            "by_sensor": by_sensor,
            "by_source_product": by_product,
            "by_confidence": by_confidence,
            "by_region": by_region,
        },
        "date_range": {
            "start": detections["acq_date_local"].min() if not detections.empty else None,
            "end": detections["acq_date_local"].max() if not detections.empty else None,
        },
        "fields": CANONICAL_COLUMNS,
        "transformations": [
            "Normalización de campos MODIS/VIIRS a esquema canónico.",
            "Confianza MODIS 0-100 -> low/nominal/high (umbrales 30/80); VIIRS l/n/h -> low/nominal/high.",
            "Asignación de provincia y región natural mediante geometrías Natural Earth (1:10m).",
            "Exclusión de detecciones fuera de las provincias de Ecuador.",
            "Fecha/hora local: UTC-5 (continental) y UTC-6 (Galápagos).",
            "Deduplicación por huella determinista (producto, satélite, fecha, hora, lat, lon).",
            "No se modifican los valores originales de confianza, FRP ni temperaturas de brillo.",
        ],
        "limitations": [
            "Una detección de foco de calor no equivale a un incendio confirmado ni a superficie quemada.",
            "MODIS (~1 km) y VIIRS (~375 m) tienen resolución, sensibilidad y horarios de pasada distintos.",
            "La ausencia de detección no implica ausencia de fuego (nubes, humo, geometría de observación).",
            "Los conteos de detecciones no son directamente comparables como área afectada.",
            "Datos SP (procesamiento estándar) y NRT (tiempo casi real) pueden diferir; se documenta el producto por registro.",
        ],
        "file": {"path": str(output.relative_to(settings.data_dir.parent)), "sha256": file_hash, "bytes": output.stat().st_size},
        "warnings": [
            warning
            for warning in [
                None
                if not (start >= date(2026, 8, 1) and end <= date(2026, 8, 31))
                else "El tramo solicitado coincide con el cambio de producto SP a NRT; revisa versiones por registro.",
            ]
            if warning
        ],
    }

    manifest_path = settings.manifest_file
    _write_manifest(manifest_path, manifest)
    _write_manifest(settings.manifests_dir / f"{manifest['dataset_version']}.json", manifest)

    if make_sample:
        sample = _build_sample(detections)
        sample_path = settings.samples_dir / "detections_sample.csv"
        _write_csv_atomic(sample, sample_path)
        sample_manifest = {
            **manifest,
            "data_mode": "sample",
            "note": "Muestra auténtica de NASA FIRMS para demo offline. No es el dataset completo.",
            "records": {**manifest["records"], "final": int(len(sample))},
            "file": {"path": str(sample_path.relative_to(settings.data_dir.parent)), "sha256": _sha256(sample_path), "bytes": sample_path.stat().st_size},
        }
        _write_manifest(settings.samples_dir / "manifest.json", sample_manifest)

    logger.info(
        "Dataset listo: %s registros | %s..%s | %.1f MB",
        len(detections),
        manifest["date_range"]["start"],
        manifest["date_range"]["end"],
        output.stat().st_size / 1024 / 1024,
    )
    return manifest
