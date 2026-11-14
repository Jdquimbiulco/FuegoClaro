"""Cliente de NASA FIRMS (Area API) con manejo de cuotas y errores."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import StringIO

import httpx
import pandas as pd

from app.core.config import get_settings
from app.domain.models import ECUADOR_BBOX, SOURCE_PLAN
from app.utils.time import parse_iso_date

logger = logging.getLogger(__name__)

BASE_URL = "https://firms.modaps.eosdis.nasa.gov/api"
MAX_DAY_RANGE = 5
# La API limita las transacciones (días solicitados) por ventana de 10 minutos.
# Con bloques de 5 días, 0.65 s entre llamadas mantiene el ritmo por debajo del límite.
REQUEST_DELAY_SECONDS = 0.65
KEY_RETRY_WAITS = (45, 90, 180)


class FirmsApiError(RuntimeError):
    """Error devuelto por NASA FIRMS; no se debe publicar un dataset parcial."""


def _looks_like_key_error(response: httpx.Response) -> bool:
    if response.status_code not in (400, 401, 403, 429):
        return False
    body = response.text.strip().lower()
    return "invalid map_key" in body or "invalid map key" in body or response.status_code in (401, 429)


@dataclass
class FetchSegment:
    source_product: str
    start: date
    end: date


class FirmsClient:
    def __init__(self, map_key: str | None = None, timeout: float = 60.0):
        self.map_key = map_key if map_key is not None else get_settings().firms_map_key
        self.timeout = timeout
        self.client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "FuegoClaro/0.1 (NASA Space Apps Challenge)"},
        )

    @property
    def configured(self) -> bool:
        return bool(self.map_key)

    def close(self) -> None:
        self.client.close()

    def _get(self, url: str, *, retries: int = 4) -> httpx.Response:
        last_error: Exception | None = None
        key_waits = iter(KEY_RETRY_WAITS)
        attempt = 0
        while attempt < retries:
            try:
                response = self.client.get(url)
                if _looks_like_key_error(response):
                    wait = next(key_waits, None)
                    if wait is None:
                        raise FirmsApiError(
                            "NASA FIRMS rechazó la MAP_KEY tras varios reintentos. "
                            "Verifica la clave o espera a que se libere la cuota."
                        )
                    logger.warning(
                        "FIRMS rechazó la MAP_KEY (%s); esperando %ss antes de reintentar",
                        response.status_code,
                        wait,
                    )
                    time.sleep(wait)
                    continue
                if response.status_code == 429 or response.status_code >= 500:
                    wait = 2**attempt
                    logger.warning("FIRMS %s; reintentando en %ss", response.status_code, wait)
                    time.sleep(wait)
                    attempt += 1
                    continue
                return response
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                wait = 2**attempt
                logger.warning("Error de red con FIRMS (%s); reintentando en %ss", exc, wait)
                time.sleep(wait)
                attempt += 1
        raise RuntimeError(f"No se pudo consultar FIRMS: {last_error}")

    def availability(self) -> dict[str, tuple[date, date]]:
        """Rango disponible por producto (SP/NRT)."""
        if not self.configured:
            raise RuntimeError("FIRMS_MAP_KEY no configurada en backend/.env")
        url = f"{BASE_URL}/data_availability/csv/{self.map_key}/ALL"
        response = self._get(url)
        response.raise_for_status()
        frame = pd.read_csv(StringIO(response.text))
        result: dict[str, tuple[date, date]] = {}
        for _, row in frame.iterrows():
            try:
                result[str(row["data_id"])] = (
                    datetime.strptime(str(row["min_date"]), "%Y-%m-%d").date(),
                    datetime.strptime(str(row["max_date"]), "%Y-%m-%d").date(),
                )
            except (ValueError, KeyError):
                continue
        return result

    def plan_segments(self, start: date, end: date, availability: dict[str, tuple[date, date]] | None = None) -> list[FetchSegment]:
        """Divide el periodo solicitado en tramos SP (calidad científica) y NRT (reciente)."""
        availability = availability or self.availability()
        segments: list[FetchSegment] = []
        for plan in SOURCE_PLAN:
            sp_range = availability.get(plan["sp"])
            nrt_range = availability.get(plan["nrt"])
            if sp_range:
                seg_start = max(start, sp_range[0])
                seg_end = min(end, sp_range[1])
                if seg_start <= seg_end:
                    segments.append(FetchSegment(plan["sp"], seg_start, seg_end))
            if nrt_range:
                # Evitar solapamiento con SP: NRT solo desde el día siguiente al máximo SP.
                nrt_start = nrt_range[0]
                if sp_range:
                    nrt_start = max(nrt_start, sp_range[1] + timedelta(days=1))
                seg_start = max(start, nrt_start)
                seg_end = min(end, nrt_range[1])
                if seg_start <= seg_end:
                    segments.append(FetchSegment(plan["nrt"], seg_start, seg_end))
        return segments

    def fetch_segment(self, segment: FetchSegment, bbox: tuple[float, float, float, float] | None = None) -> pd.DataFrame:
        """Descarga un tramo en bloques de 5 días (límite del Area API)."""
        if not self.configured:
            raise RuntimeError("FIRMS_MAP_KEY no configurada en backend/.env")
        west, south, east, north = bbox or ECUADOR_BBOX
        area = f"{west},{south},{east},{north}"
        frames: list[pd.DataFrame] = []
        cursor = segment.start
        while cursor <= segment.end:
            url = f"{BASE_URL}/area/csv/{self.map_key}/{segment.source_product}/{area}/{MAX_DAY_RANGE}/{cursor.isoformat()}"
            logger.info("FIRMS %s %s", segment.source_product, cursor.isoformat())
            response = self._get(url)
            if response.status_code != 200:
                raise FirmsApiError(
                    f"FIRMS respondió {response.status_code} para {segment.source_product} {cursor}: "
                    f"{response.text[:200].strip()}"
                )
            if response.text.lstrip().lower().startswith("invalid api call"):
                raise FirmsApiError(
                    f"FIRMS devolvió 'Invalid API call' para {segment.source_product} {cursor}: {response.text[:200]}"
                )
            if response.text.strip():
                try:
                    frame = pd.read_csv(StringIO(response.text))
                except Exception as exc:  # CSV malformado
                    raise FirmsApiError(
                        f"CSV inválido de FIRMS para {segment.source_product} {cursor}: {exc}"
                    ) from exc
                if not frame.empty:
                    # El bloque de 5 días puede exceder el final del segmento.
                    frame["acq_date"] = frame["acq_date"].astype(str)
                    mask = (frame["acq_date"] >= segment.start.isoformat()) & (
                        frame["acq_date"] <= segment.end.isoformat()
                    )
                    frames.append(frame[mask])
            cursor += timedelta(days=MAX_DAY_RANGE)
            time.sleep(REQUEST_DELAY_SECONDS)

        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        logger.info("  -> %s registros (%s)", len(combined), segment.source_product)
        return combined

    def fetch_all(
        self,
        start: date,
        end: date,
        bbox: tuple[float, float, float, float] | None = None,
        *,
        availability: dict[str, tuple[date, date]] | None = None,
    ) -> tuple[list[tuple[str, pd.DataFrame]], list[dict]]:
        """Descarga todos los tramos y devuelve [(producto, dataframe)] + reporte."""
        segments = self.plan_segments(start, end, availability)
        results: list[tuple[str, pd.DataFrame]] = []
        report: list[dict] = []
        for segment in segments:
            frame = self.fetch_segment(segment, bbox=bbox)
            results.append((segment.source_product, frame))
            report.append(
                {
                    "source_product": segment.source_product,
                    "start": segment.start.isoformat(),
                    "end": segment.end.isoformat(),
                    "records": int(len(frame)),
                }
            )
        return results, report
