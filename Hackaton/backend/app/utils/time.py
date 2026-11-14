"""Utilidades de fechas y periodos comparables."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

ECUADOR_MAINLAND_TZ_OFFSET = -5  # America/Guayaquil
GALAPAGOS_TZ_OFFSET = -6  # Pacific/Galapagos


def parse_iso_date(value: str, field: str = "fecha") -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field} inválida: '{value}'. Formato esperado YYYY-MM-DD.") from exc


def today_utc() -> date:
    return datetime.now(timezone.utc).date()


def date_range(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")
    days = (end - start).days
    return [start + timedelta(days=i) for i in range(days + 1)]


def month_bounds(year: int, month: int) -> tuple[date, date]:
    if not 1 <= month <= 12:
        raise ValueError("Mes inválido.")
    start = date(year, month, 1)
    end = date(year + (month == 12), (month % 12) + 1, 1) - timedelta(days=1)
    return start, end


def period_label(start: str, end: str) -> str:
    return f"{start} a {end}"


def days_between(start: str, end: str) -> int:
    return (parse_iso_date(end) - parse_iso_date(start)).days + 1
