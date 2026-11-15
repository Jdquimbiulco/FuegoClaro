"""Resumen compuesto que reutiliza las agregaciones y los módulos nuevos."""

from __future__ import annotations

from app.domain.aggregation import build_summary, build_timeseries
from app.domain.dtos import AnalyticsSummaryDTO
from app.domain.models import FilterSpec
from app.services import fire_events_service, susceptibility_service
from app.services.data_store import get_store


def summary(spec: FilterSpec) -> tuple[AnalyticsSummaryDTO, dict[str, str]]:
    store = get_store()
    detections = build_summary(store.df, spec)
    events, total_events = fire_events_service.list_events(spec, limit=5000)
    risk_map = susceptibility_service.get_map()
    risk_distribution = {"Bajo": 0, "Medio": 0, "Alto": 0, "Extremo": 0}
    risk_distribution.update(risk_map.summary.get("by_risk", {}))
    by_sensor = []
    for row in detections["by_sensor"]:
        by_sensor.append({
            "sensor": row["sensor"], "count": row["count"], "share": row["share"],
            "frp_sum_mw": row.get("frp_sum"), "frp_mean_mw": row.get("frp_mean"),
        })
    critical = [event for event in events if event.nivel_alerta == "alerta_roja"]
    modules = {
        "detections": "available" if not store.df.empty else "pending",
        "clustering": fire_events_service.module_info().status,
        "susceptibility": "available" if risk_map.features else "pending",
    }
    dto = AnalyticsSummaryDTO(
        period=detections["period"],
        kpis={
            "detections_total": detections["total"],
            "active_days": detections["active_days"],
            "fire_events_total": total_events,
            "critical_events": len(critical),
            "extreme_risk_areas": int(risk_distribution.get("Extremo", 0)),
            "provinces_affected": len(detections["by_province"]),
            "frp_total_mw": detections["frp"]["sum"],
        },
        by_sensor=by_sensor,
        by_region=detections["by_region"],
        by_severity={
            level: sum(event.nivel_alerta == level for event in events)
            for level in ("alerta_roja", "alerta_media", "quema_menor")
        },
        risk_distribution=risk_distribution,
        timeseries=build_timeseries(store.df, spec, granularity="day")["series"],
        alerts=[event.model_dump(exclude={"geometria", "puntos_ids"}) for event in critical[:10]],
        top_provinces=detections["by_province"],
        notes=[
            "El resumen es exploratorio; las detecciones y eventos no confirman incendios ni cuantifican superficie quemada.",
            *(["La distribución de riesgo está vacía porque el mapa agregado aún no está disponible."] if not risk_map.features else []),
        ],
    )
    return dto, modules
