"""Contratos Pydantic compartidos entre dominio, servicios y API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class FireEventDTO(BaseModel):
    id_evento: str
    frp_total: float
    frp_max: float
    frp_medio: float
    puntos_count: int
    geometria: dict[str, Any]
    centro: tuple[float, float]
    inicio: str | None
    fin: str | None
    dias: list[str]
    diurnas: int
    nocturnas: int
    sensores: list[str]
    provincias: list[str]
    puntos_ids: list[str] = Field(default_factory=list)
    contraste_medio_k: float | None
    nivel_alerta: str
    nivel_alerta_label: str
    motivo_regla: str
    rank: int
    province_names: list[str] = Field(default_factory=list)
    region_id: str | None = None
    region: str | None = None
    canton: str | None = None
    confidence_by_level: dict[str, int] = Field(default_factory=dict)
    confidence_dominant: str | None = None
    evidence_score_max: int | None = None
    context_flags: list[str] = Field(default_factory=list)
    hull_area_km2: float | None = None


class FireDashboardDTO(BaseModel):
    period: dict[str, str]
    summary: dict[str, int | float | None]
    events: list[FireEventDTO]
    by_province: list[dict[str, str | int]]
    series: list[dict[str, Any]]
    seasonality: list[dict[str, str | int]]
    history_period: dict[str, str | None]
    notes: list[str]


class PointRiskDTO(BaseModel):
    cell_id: str
    latitude: float
    longitude: float
    cell_center: dict[str, float | None]
    distance_to_cell_km: float
    date: str
    window_days: int
    probability: float
    risk_level: str
    thresholds: dict[str, Any]
    model_version: str | None = None
    calibration: Any = None
    data_completeness: float
    top_factors: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str


class SusceptibilityMapDTO(BaseModel):
    level: str
    type: str = "FeatureCollection"
    features: list[dict[str, Any]] = Field(default_factory=list)
    model: dict[str, Any] = Field(default_factory=dict)
    risk_bands: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class AnalyticsSummaryDTO(BaseModel):
    period: dict[str, str | int]
    kpis: dict[str, int | float | None]
    by_sensor: list[dict[str, Any]] = Field(default_factory=list)
    by_region: list[dict[str, Any]] = Field(default_factory=list)
    by_severity: dict[str, int] = Field(default_factory=dict)
    risk_distribution: dict[str, int] = Field(default_factory=dict)
    timeseries: list[dict[str, Any]] = Field(default_factory=list)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    top_provinces: list[dict[str, Any]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
