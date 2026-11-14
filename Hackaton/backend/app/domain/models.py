"""Modelos y constantes de dominio de FuegoClaro."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Sensor(StrEnum):
    MODIS = "MODIS"
    VIIRS = "VIIRS"


class ConfidenceLevel(StrEnum):
    LOW = "low"
    NOMINAL = "nominal"
    HIGH = "high"
    UNKNOWN = "unknown"


CONFIDENCE_LEVELS = [ConfidenceLevel.LOW, ConfidenceLevel.NOMINAL, ConfidenceLevel.HIGH, ConfidenceLevel.UNKNOWN]

NATURAL_REGIONS: dict[str, dict] = {
    "costa": {"name": "Costa", "description": "Llanura costera y estribaciones occidentales"},
    "sierra": {"name": "Sierra", "description": "Cordillera de los Andes y valles interandinos"},
    "amazonia": {"name": "Amazonía", "description": "Cuenca amazónica y estribaciones orientales"},
    "galapagos": {"name": "Galápagos", "description": "Archipiélago de Galápagos"},
}

# Provincia (código ISO 3166-2) -> (nombre canónico, región natural)
PROVINCES: dict[str, tuple[str, str]] = {
    "EC-E": ("Esmeraldas", "costa"),
    "EC-M": ("Manabí", "costa"),
    "EC-SD": ("Santo Domingo de los Tsáchilas", "costa"),
    "EC-R": ("Los Ríos", "costa"),
    "EC-G": ("Guayas", "costa"),
    "EC-SE": ("Santa Elena", "costa"),
    "EC-O": ("El Oro", "costa"),
    "EC-C": ("Carchi", "sierra"),
    "EC-I": ("Imbabura", "sierra"),
    "EC-P": ("Pichincha", "sierra"),
    "EC-X": ("Cotopaxi", "sierra"),
    "EC-T": ("Tungurahua", "sierra"),
    "EC-B": ("Bolívar", "sierra"),
    "EC-H": ("Chimborazo", "sierra"),
    "EC-F": ("Cañar", "sierra"),
    "EC-A": ("Azuay", "sierra"),
    "EC-L": ("Loja", "sierra"),
    "EC-U": ("Sucumbíos", "amazonia"),
    "EC-N": ("Napo", "amazonia"),
    "EC-D": ("Orellana", "amazonia"),
    "EC-Y": ("Pastaza", "amazonia"),
    "EC-S": ("Morona Santiago", "amazonia"),
    "EC-Z": ("Zamora Chinchipe", "amazonia"),
    "EC-W": ("Galápagos", "galapagos"),
}

# Periodo usado por la ingesta por defecto (configurable por CLI)
DEFAULT_START_DATE = "2022-01-01"
DEFAULT_END_DATE = "2026-11-12"

# Bounding box amplio que contiene Ecuador continental y Galápagos.
# Se filtra por geometrías provinciales antes de publicar los datos.
ECUADOR_BBOX = (-92.5, -5.5, -74.5, 2.0)

# Plan de productos: series históricas homogéneas + NRT para el tramo reciente.
SOURCE_PLAN = [
    {
        "sensor": Sensor.MODIS,
        "sp": "MODIS_SP",
        "nrt": "MODIS_NRT",
        "label": "MODIS Collection 6.1 (Terra/Aqua, ~1 km)",
    },
    {
        "sensor": Sensor.VIIRS,
        "sp": "VIIRS_NOAA20_SP",
        "nrt": "VIIRS_NOAA20_NRT",
        "label": "VIIRS 375 m (NOAA-20)",
    },
]


@dataclass
class FilterSpec:
    start_date: str
    end_date: str
    region_id: str | None = None
    sensor: str | None = None
    confidence: list[str] = field(default_factory=list)
    daynight: str | None = None
    min_frp: float | None = None
    bbox: tuple[float, float, float, float] | None = None
