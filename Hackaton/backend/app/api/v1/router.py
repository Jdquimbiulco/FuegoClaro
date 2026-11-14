"""Router de la API v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import anomalies, calendar, comparison, detections, export, health, insights, meta, stats

router = APIRouter()
router.include_router(health.router)
router.include_router(meta.router)
router.include_router(detections.router)
router.include_router(stats.router)
router.include_router(calendar.router)
router.include_router(comparison.router)
router.include_router(anomalies.router)
router.include_router(insights.router)
router.include_router(export.router)
