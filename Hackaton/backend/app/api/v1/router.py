"""Router de la API v1."""

from fastapi import APIRouter

from app.api.v1.endpoints import analytics, anomalies, calendar, comparison, detections, export, fire_events, health, insights, meta, stats, susceptibility

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
router.include_router(fire_events.router)
router.include_router(susceptibility.router)
router.include_router(analytics.router)
