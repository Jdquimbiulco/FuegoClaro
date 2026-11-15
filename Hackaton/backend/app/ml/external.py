"""Fuentes externas del pipeline de riesgo: clima, precipitación, DEM y NDVI (100 % NASA / abiertas).

Versión histórica orientada a evitar límites de peticiones (HTTP 429):

- **NASA POWER** (sin API key): clima diario histórico. Los datos vienen de la malla
  MERRA-2 (0,5° x 0,625°), así que las celdas se **deduplican** a esa malla y se hace
  una consulta por punto único, no por celda.
- **GPM IMERG** (token Earthdata, opcional): precipitación diaria 0,1° vía ``earthaccess``.
- **DEM local** (Copernicus GLO-30, público en AWS): elevación, pendiente y aspecto sin API.
- **NASA AppEEARS** (token Earthdata): NDVI de MODIS MOD13Q1 cada 16 días.

Todas las descargas se cachean en ``data/cache`` y son reanudables. El pipeline no depende
de que una fuente esté disponible: si NDVI falla, el dataset se genera con
``ndvi_available=0`` y una advertencia en el manifiesto.

Notas sobre equivalencias con las columnas antiguas de Open-Meteo (ver ``WEATHER_SOURCE_NOTES``):
varias variables son aproximaciones o no existen en POWER. Si ya entrenaste modelos con
Open-Meteo, regenera el dataset y reentrena: las escalas y la resolución cambian.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import math
import os
import time
import zipfile
from pathlib import Path
from typing import Iterable

import httpx
import numpy as np
import pandas as pd

from app.core.config import get_settings

logger = logging.getLogger(__name__)

POWER_DAILY_POINT = "https://power.larc.nasa.gov/api/temporal/daily/point"
APPEEARS_BASE = "https://appeears.earthdatacloud.nasa.gov/api"
COPERNICUS_DEM_URL = "https://copernicus-dem-30m.s3.amazonaws.com/{name}/{name}.tif"

# Malla nativa de MERRA-2 (la que usa POWER): lat cada 0,5°, lon cada 0,625°.
POWER_LAT_STEP = 0.5
POWER_LON_STEP = 0.625
POWER_FILL = -999.0

# Parámetros de POWER solicitados (comunidad AG).
POWER_PARAMETERS = [
    "T2M_MAX",
    "T2M_MIN",
    "T2M",
    "RH2M",
    "WS10M_MAX",
    "PRECTOTCORR",
    "ALLSKY_SFC_SW_DWN",
    "GWETTOP",
    "GWETROOT",
]

# Columnas de salida (mismos nombres que usaba el pipeline con Open-Meteo).
WEATHER_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "temperature_2m_mean",
    "relative_humidity_2m_mean",
    "relative_humidity_2m_min",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
    "precipitation_sum",
    "vapor_pressure_deficit_max",
    "et0_fao_evapotranspiration",
    "soil_moisture_0_to_7cm_mean",
    "soil_moisture_7_to_28cm_mean",
    "shortwave_radiation_sum",
]

WEATHER_SOURCE_NOTES = {
    "temperature_2m_max/min/mean": "POWER T2M_MAX / T2M_MIN / T2M (°C).",
    "relative_humidity_2m_mean": "POWER RH2M (%).",
    "relative_humidity_2m_min": "No disponible en POWER diario: NaN.",
    "wind_speed_10m_max": "POWER WS10M_MAX (m/s).",
    "wind_gusts_10m_max": "No disponible en POWER: NaN.",
    "precipitation_sum": "POWER PRECTOTCORR (mm/día). Puede sustituirse por IMERG (ImergClient).",
    "vapor_pressure_deficit_max": "Aproximado (kPa): es(Tmax) - RH2M/100 * es(Tmean).",
    "et0_fao_evapotranspiration": "Hargreaves-Samani (mm/día) con Tmax, Tmin y radiación extraterrestre.",
    "soil_moisture_0_to_7cm_mean": "POWER GWETTOP: humedad relativa del suelo superficial (0-1), no m3/m3.",
    "soil_moisture_7_to_28cm_mean": "POWER GWETROOT: humedad relativa de la zona radicular (0-1), no m3/m3.",
    "shortwave_radiation_sum": "POWER ALLSKY_SFC_SW_DWN (kWh/m2/día) convertido a MJ/m2/día.",
}


# --------------------------------------------------------------------------- utilidades
def _hash_key(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _cache_file(root: Path, namespace: str, key: str, suffix: str = ".parquet") -> Path:
    folder = root / namespace
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{key}{suffix}"


def _retry_after_seconds(response: httpx.Response, attempt: int, cap: float = 300.0) -> float:
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(cap, max(1.0, float(header)))
        except ValueError:
            pass
    return min(cap, 5.0 * (2**attempt))


def _request(
    method: str,
    url: str,
    *,
    max_retries: int = 5,
    timeout: float = 120.0,
    **kwargs,
) -> httpx.Response:
    """Petición HTTP con reintentos; respeta ``Retry-After`` en 429 y reintenta 5xx."""
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                response = client.request(method, url, **kwargs)
            if response.status_code == 429 or response.status_code >= 500:
                wait = _retry_after_seconds(response, attempt)
                logger.warning(
                    "HTTP %s en %s; reintento %s/%s en %.0fs",
                    response.status_code,
                    url,
                    attempt + 1,
                    max_retries,
                    wait,
                )
                last_error = RuntimeError(f"HTTP {response.status_code}")
                if attempt < max_retries - 1:
                    time.sleep(wait)
                    continue
                break
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError:
            raise
        except Exception as exc:  # noqa: BLE001 - red/timeout: se registra y se reintenta
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(min(60.0, 2.0**attempt))
    raise RuntimeError(f"{method} {url} falló tras {max_retries} intentos: {last_error}")


def timezone_for_cell(row) -> str:
    region = str(getattr(row, "region_id", "") or "")
    return "Pacific/Galapagos" if region == "galapagos" else "America/Guayaquil"


def _snap(values: pd.Series, step: float, offset: float = 0.0) -> pd.Series:
    """Lleva coordenadas al centro más cercano de una malla regular."""
    return ((values - offset) / step).round() * step + offset


def _year_ranges(start: str, end: str, span: int = 5) -> list[tuple[str, str]]:
    first, last = pd.Timestamp(start), pd.Timestamp(end)
    ranges: list[tuple[str, str]] = []
    cursor = first
    while cursor <= last:
        stop = min(last, pd.Timestamp(year=cursor.year + span - 1, month=12, day=31))
        ranges.append((cursor.strftime("%Y-%m-%d"), stop.strftime("%Y-%m-%d")))
        cursor = stop + pd.Timedelta(days=1)
    return ranges


# ------------------------------------------------------------------- clima: NASA POWER
def _saturation_vapor_pressure(temp_c: pd.Series | np.ndarray) -> np.ndarray:
    temp = np.asarray(temp_c, dtype=float)
    return 0.6108 * np.exp(17.27 * temp / (temp + 237.3))


def _extraterrestrial_radiation(lat_deg: float, day_of_year: np.ndarray) -> np.ndarray:
    """Radiación extraterrestre diaria (MJ/m2/día), FAO-56."""
    phi = math.radians(lat_deg)
    doy = np.asarray(day_of_year, dtype=float)
    dr = 1.0 + 0.033 * np.cos(2.0 * np.pi / 365.0 * doy)
    delta = 0.409 * np.sin(2.0 * np.pi / 365.0 * doy - 1.39)
    ws = np.arccos(np.clip(-math.tan(phi) * np.tan(delta), -1.0, 1.0))
    return (24.0 * 60.0 / np.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * np.sin(delta) + math.cos(phi) * np.cos(delta) * np.sin(ws)
    )


class NasaPowerClient:
    """Clima diario histórico con NASA POWER (sin API key), con caché en disco.

    Consulta **un punto por celda de la malla MERRA-2**, no uno por celda del proyecto,
    y reparte el resultado a todas las celdas que caen dentro.
    """

    def __init__(
        self,
        cache_dir: Path | None = None,
        *,
        sleep_seconds: float = 1.0,
        max_retries: int = 5,
        timeout: float = 120.0,
        community: str = "AG",
        years_per_request: int = 5,
    ) -> None:
        self.cache_dir = Path(cache_dir or get_settings().cache_dir)
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.timeout = timeout
        self.community = community
        self.years_per_request = years_per_request

    # ---------------------------------------------------------------- malla única
    @staticmethod
    def snap_cells(cells: pd.DataFrame) -> pd.DataFrame:
        """Añade ``plat``/``plon`` (centro de la malla MERRA-2 de cada celda)."""
        frame = cells.copy()
        frame["plat"] = _snap(frame["lat"].astype(float), POWER_LAT_STEP).round(4)
        frame["plon"] = _snap(frame["lon"].astype(float), POWER_LON_STEP).round(4)
        return frame

    # ---------------------------------------------------------------- un punto
    def _fetch_point(self, lat: float, lon: float, start: str, end: str, refresh: bool) -> pd.DataFrame:
        key = _hash_key({"lat": lat, "lon": lon, "start": start, "end": end, "p": POWER_PARAMETERS, "v": 1})
        cached = _cache_file(self.cache_dir, "power/daily", key)
        if cached.exists() and not refresh:
            return pd.read_parquet(cached)

        params = {
            "parameters": ",".join(POWER_PARAMETERS),
            "community": self.community,
            "latitude": f"{lat:.4f}",
            "longitude": f"{lon:.4f}",
            "start": pd.Timestamp(start).strftime("%Y%m%d"),
            "end": pd.Timestamp(end).strftime("%Y%m%d"),
            "format": "JSON",
        }
        response = _request(
            "GET",
            POWER_DAILY_POINT,
            params=params,
            max_retries=self.max_retries,
            timeout=self.timeout,
        )
        parameter = (response.json().get("properties") or {}).get("parameter") or {}
        if not parameter:
            return pd.DataFrame()
        raw = pd.DataFrame(parameter)
        raw.index = pd.to_datetime(raw.index, format="%Y%m%d", errors="coerce")
        raw = raw[raw.index.notna()].replace(POWER_FILL, np.nan)
        raw = raw.dropna(how="all")
        if raw.empty:
            return pd.DataFrame()
        result = self._to_weather_columns(raw, lat)
        result.to_parquet(cached, index=False)
        time.sleep(self.sleep_seconds)
        return result

    @staticmethod
    def _to_weather_columns(raw: pd.DataFrame, lat: float) -> pd.DataFrame:
        def col(name: str) -> pd.Series:
            return raw[name] if name in raw.columns else pd.Series(np.nan, index=raw.index)

        tmax, tmin, tmean = col("T2M_MAX"), col("T2M_MIN"), col("T2M")
        rh = col("RH2M")
        es_max = _saturation_vapor_pressure(tmax)
        ea = rh.to_numpy() / 100.0 * _saturation_vapor_pressure(tmean)
        vpd_max = np.clip(es_max - ea, 0.0, None)

        ra = _extraterrestrial_radiation(lat, raw.index.dayofyear.to_numpy())
        et0 = 0.0023 * 0.408 * ra * (tmean.to_numpy() + 17.8) * np.sqrt(
            np.clip((tmax - tmin).to_numpy(), 0.0, None)
        )

        out = pd.DataFrame(
            {
                "date": raw.index.strftime("%Y-%m-%d"),
                "temperature_2m_max": tmax.to_numpy(),
                "temperature_2m_min": tmin.to_numpy(),
                "temperature_2m_mean": tmean.to_numpy(),
                "relative_humidity_2m_mean": rh.to_numpy(),
                "relative_humidity_2m_min": np.nan,
                "wind_speed_10m_max": col("WS10M_MAX").to_numpy(),
                "wind_gusts_10m_max": np.nan,
                "precipitation_sum": col("PRECTOTCORR").to_numpy(),
                "vapor_pressure_deficit_max": vpd_max,
                "et0_fao_evapotranspiration": et0,
                "soil_moisture_0_to_7cm_mean": col("GWETTOP").to_numpy(),
                "soil_moisture_7_to_28cm_mean": col("GWETROOT").to_numpy(),
                "shortwave_radiation_sum": col("ALLSKY_SFC_SW_DWN").to_numpy() * 3.6,
            }
        )
        return out

    # --------------------------------------------------------------- API pública
    def daily_weather(
        self,
        cells: pd.DataFrame,
        start: str,
        end: str,
        *,
        forecast: bool = False,
        refresh: bool = False,
        chunk_size: int | None = None,  # compatibilidad con la firma anterior (se ignora)
    ) -> pd.DataFrame:
        """Clima diario por celda. ``cells`` necesita ``cell_id``, ``lat`` y ``lon``.

        Devuelve ``cell_id``, ``date`` y ``WEATHER_VARIABLES``. Solo histórico:
        POWER no ofrece pronóstico.
        """
        if forecast:
            raise NotImplementedError("NASA POWER es solo histórico; no ofrece pronóstico.")
        empty = pd.DataFrame(columns=["cell_id", "date", *WEATHER_VARIABLES])
        if cells.empty:
            return empty

        snapped = self.snap_cells(cells[["cell_id", "lat", "lon"]])
        unique_points = snapped[["plat", "plon"]].drop_duplicates().reset_index(drop=True)
        ranges = _year_ranges(start, end, self.years_per_request)
        logger.info(
            "POWER: %s celdas -> %s puntos únicos de malla x %s tramos",
            len(snapped),
            len(unique_points),
            len(ranges),
        )

        pieces: list[pd.DataFrame] = []
        for position, point in enumerate(unique_points.itertuples(index=False), start=1):
            for range_start, range_end in ranges:
                try:
                    frame = self._fetch_point(point.plat, point.plon, range_start, range_end, refresh)
                except Exception as exc:  # noqa: BLE001 - un punto no debe romper el dataset
                    logger.warning(
                        "POWER: punto (%s, %s) %s..%s falló: %s", point.plat, point.plon, range_start, range_end, exc
                    )
                    continue
                if frame.empty:
                    continue
                frame = frame.copy()
                frame["plat"], frame["plon"] = point.plat, point.plon
                pieces.append(frame)
            if position % 25 == 0:
                logger.info("POWER: %s/%s puntos", position, len(unique_points))

        if not pieces:
            return empty
        by_point = pd.concat(pieces, ignore_index=True).drop_duplicates(["plat", "plon", "date"])
        merged = snapped[["cell_id", "plat", "plon"]].merge(by_point, on=["plat", "plon"], how="inner")
        return merged.drop(columns=["plat", "plon"])[["cell_id", "date", *WEATHER_VARIABLES]].reset_index(drop=True)


# Alias para sustituir al cliente anterior sin tocar los imports del pipeline.
OpenMeteoClient = NasaPowerClient


# -------------------------------------------------------------- lluvia: GPM IMERG (opcional)
class ImergClient:
    """Precipitación diaria GPM IMERG V07 (0,1°) con ``earthaccess``; devuelve ``precipitation_imerg``.

    Se procesa mes a mes y se cachea el resultado por punto único de malla, de modo que el
    número de celdas no afecta a las llamadas. ``short_name="GPM_3IMERGDL"`` es Late Run
    (latencia de horas); ``"GPM_3IMERGDF"`` es Final Run (calibrado con pluviómetros, meses de
    latencia). Para histórico, Final es preferible.
    """

    GRID_STEP = 0.1

    def __init__(self, cache_dir: Path | None = None, *, short_name: str = "GPM_3IMERGDF", version: str = "07") -> None:
        settings = get_settings()
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.short_name = short_name
        self.version = version
        self._token = getattr(settings, "earthdata_token", None)
        self._logged_in = False

    def _login(self) -> bool:
        if self._logged_in:
            return True
        try:
            import earthaccess  # import perezoso: dependencia opcional
        except ImportError:
            logger.warning("IMERG: instala 'earthaccess' (pip install earthaccess xarray h5netcdf); se omite")
            return False
        if self._token:
            os.environ.setdefault("EARTHDATA_TOKEN", self._token)
        try:
            auth = earthaccess.login(strategy="environment")
        except Exception as exc:  # noqa: BLE001
            logger.warning("IMERG: login Earthdata falló (%s); se omite", exc)
            return False
        self._logged_in = bool(getattr(auth, "authenticated", True))
        return self._logged_in

    @staticmethod
    def _snap_imerg(values: pd.Series) -> pd.Series:
        # Centros IMERG: ...,-0.05, 0.05, 0.15, ... (celda de 0,1° con centro en x.x5)
        return (np.floor(values / ImergClient.GRID_STEP) * ImergClient.GRID_STEP + ImergClient.GRID_STEP / 2).round(3)

    def daily_precipitation(self, cells: pd.DataFrame, start: str, end: str, *, refresh: bool = False) -> pd.DataFrame:
        """Devuelve ``cell_id``, ``date`` y ``precipitation_imerg`` (mm/día)."""
        empty = pd.DataFrame(columns=["cell_id", "date", "precipitation_imerg"])
        if cells.empty or not self._login():
            return empty

        import earthaccess
        import xarray as xr

        frame = cells[["cell_id", "lat", "lon"]].copy()
        frame["ilat"] = self._snap_imerg(frame["lat"].astype(float))
        frame["ilon"] = self._snap_imerg(frame["lon"].astype(float))
        points = frame[["ilat", "ilon"]].drop_duplicates().reset_index(drop=True)

        months = pd.period_range(start=pd.Timestamp(start), end=pd.Timestamp(end), freq="M")
        pieces: list[pd.DataFrame] = []
        for period in months:
            m_start = max(period.start_time, pd.Timestamp(start)).strftime("%Y-%m-%d")
            m_end = min(period.end_time, pd.Timestamp(end)).strftime("%Y-%m-%d")
            key = _hash_key(
                {
                    "p": [[float(a), float(b)] for a, b in zip(points["ilat"], points["ilon"])],
                    "start": m_start,
                    "end": m_end,
                    "product": self.short_name,
                    "version": self.version,
                    "v": 1,
                }
            )
            cached = _cache_file(self.cache_dir, "imerg", key)
            if cached.exists() and not refresh:
                pieces.append(pd.read_parquet(cached))
                continue
            try:
                granules = earthaccess.search_data(
                    short_name=self.short_name,
                    version=self.version,
                    temporal=(m_start, m_end),
                    bounding_box=(
                        float(frame["lon"].min()) - 0.2,
                        float(frame["lat"].min()) - 0.2,
                        float(frame["lon"].max()) + 0.2,
                        float(frame["lat"].max()) + 0.2,
                    ),
                )
                if not granules:
                    continue
                files = earthaccess.open(granules)
                with xr.open_mfdataset(files, combine="by_coords") as ds:
                    variable = next((v for v in ("precipitation", "precipitationCal") if v in ds), None)
                    if variable is None:
                        raise KeyError(f"sin variable de precipitación en {list(ds.data_vars)}")
                    sampled = ds[variable].sel(
                        lat=xr.DataArray(points["ilat"].to_numpy(), dims="pt"),
                        lon=xr.DataArray(points["ilon"].to_numpy(), dims="pt"),
                        method="nearest",
                    ).load()
                    index = ds.indexes["time"]
                    if hasattr(index, "to_datetimeindex"):
                        index = index.to_datetimeindex()
                    dates = pd.DatetimeIndex(index).normalize().strftime("%Y-%m-%d")
                values = np.asarray(sampled.transpose("time", "pt").values, dtype=float)
                values[values < 0] = np.nan  # relleno del producto
                month = pd.DataFrame(
                    {
                        "ilat": np.tile(points["ilat"].to_numpy(), len(dates)),
                        "ilon": np.tile(points["ilon"].to_numpy(), len(dates)),
                        "date": np.repeat(dates.to_numpy(), len(points)),
                        "precipitation_imerg": values.reshape(-1),
                    }
                )
                month.to_parquet(cached, index=False)
                pieces.append(month)
            except Exception as exc:  # noqa: BLE001 - un mes fallido no rompe el dataset
                logger.warning("IMERG: mes %s falló (%s); se continúa", period, exc)

        if not pieces:
            return empty
        by_point = pd.concat(pieces, ignore_index=True).drop_duplicates(["ilat", "ilon", "date"])
        merged = frame[["cell_id", "ilat", "ilon"]].merge(by_point, on=["ilat", "ilon"], how="inner")
        return merged[["cell_id", "date", "precipitation_imerg"]].reset_index(drop=True)


# ------------------------------------------------------------------- terreno: DEM local
def build_dem_mosaic(bbox: tuple[float, float, float, float], out_path: Path | str, *, tiles_dir: Path | str | None = None) -> Path:
    """Descarga y une las teselas Copernicus GLO-30 (AWS público, sin token) que cubren ``bbox``.

    ``bbox`` = (oeste, sur, este, norte) en grados. Se ejecuta una sola vez; luego
    ``DemProvider`` lee el GeoTIFF resultante sin ninguna llamada de red.
    Requiere ``rasterio``.
    """
    import rasterio
    from rasterio.merge import merge

    west, south, east, north = bbox
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tiles_dir = Path(tiles_dir or out_path.parent / "dem_tiles")
    tiles_dir.mkdir(parents=True, exist_ok=True)

    tile_paths: list[Path] = []
    for lat in range(math.floor(south), math.floor(north) + 1):
        for lon in range(math.floor(west), math.floor(east) + 1):
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            name = f"Copernicus_DSM_COG_10_{ns}{abs(lat):02d}_00_{ew}{abs(lon):03d}_00_DEM"
            target = tiles_dir / f"{name}.tif"
            if not target.exists():
                try:
                    response = _request("GET", COPERNICUS_DEM_URL.format(name=name), timeout=600.0)
                except Exception as exc:  # noqa: BLE001 - teselas oceánicas no existen
                    logger.info("DEM: tesela %s no disponible (%s)", name, exc)
                    continue
                target.write_bytes(response.content)
            tile_paths.append(target)

    if not tile_paths:
        raise RuntimeError("No se pudo obtener ninguna tesela del DEM para ese bbox")
    sources = [rasterio.open(path) for path in tile_paths]
    try:
        mosaic, transform = merge(sources)
        profile = sources[0].profile.copy()
        profile.update(height=mosaic.shape[1], width=mosaic.shape[2], transform=transform, compress="deflate")
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(mosaic)
    finally:
        for source in sources:
            source.close()
    return out_path


class DemProvider:
    """Elevación, pendiente, aspecto y rugosidad a partir de un DEM local (GeoTIFF).

    Usa el mismo esquema que la versión anterior (9 puntos alrededor de cada celda), pero
    leyendo el raster local: cero llamadas de red. Si no se indica ``dem_path`` se busca en
    ``settings.dem_path``, en la variable de entorno ``DEM_PATH`` y en ``<cache>/dem/dem.tif``.
    """

    def __init__(self, client=None, cache_dir: Path | None = None, dem_path: Path | str | None = None) -> None:
        settings = get_settings()
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        candidate = dem_path or getattr(settings, "dem_path", None) or os.environ.get("DEM_PATH")
        self.dem_path = Path(candidate) if candidate else self.cache_dir / "dem" / "dem.tif"

    def terrain(self, cells: pd.DataFrame, *, refresh: bool = False, step: float = 0.1) -> pd.DataFrame:
        import rasterio

        if not self.dem_path.exists():
            raise FileNotFoundError(
                f"No existe el DEM local en {self.dem_path}. Genera uno con build_dem_mosaic(bbox, ruta) "
                "o define DEM_PATH."
            )
        cache = _cache_file(
            self.cache_dir,
            "dem",
            _hash_key({"cells": sorted(cells["cell_id"].tolist()), "step": step, "dem": str(self.dem_path), "v": 2}),
        )
        if cache.exists() and not refresh:
            return pd.read_parquet(cache)

        delta = max(step * 0.1, 0.005)
        offsets = [
            ("center", 0.0, 0.0),
            ("n", delta, 0.0),
            ("s", -delta, 0.0),
            ("e", 0.0, delta),
            ("w", 0.0, -delta),
            ("ne", delta, delta),
            ("nw", delta, -delta),
            ("se", -delta, delta),
            ("sw", -delta, -delta),
        ]

        cell_ids = cells["cell_id"].to_numpy()
        lats = cells["lat"].to_numpy(dtype=float)
        lons = cells["lon"].to_numpy(dtype=float)

        samples: dict[str, np.ndarray] = {}
        with rasterio.open(self.dem_path) as dem:
            nodata = dem.nodata
            for name, dlat, dlon in offsets:
                coords = list(zip(lons + dlon, lats + dlat))
                values = np.array([v[0] for v in dem.sample(coords)], dtype=float)
                if nodata is not None:
                    values[values == nodata] = np.nan
                values[values < -500] = np.nan  # relleno típico de DEM
                samples[name] = values

        lat_m = delta * 111_320.0
        lon_m = delta * 111_320.0 * np.cos(np.radians(lats))
        dz_dx = (samples["e"] - samples["w"]) / (2.0 * lon_m)
        dz_dy = (samples["n"] - samples["s"]) / (2.0 * lat_m)
        aspect = np.degrees(np.arctan2(dz_dy, -dz_dx))
        stacked = np.vstack([samples[name] for name, _, _ in offsets])

        result = pd.DataFrame(
            {
                "cell_id": cell_ids,
                "elevation_m": samples["center"],
                "slope_deg": np.degrees(np.arctan(np.sqrt(dz_dx**2 + dz_dy**2))),
                "aspect_sin": np.sin(np.radians(aspect)),
                "aspect_cos": np.cos(np.radians(aspect)),
                "terrain_roughness": np.nanstd(stacked, axis=0, ddof=1),
            }
        )
        result.to_parquet(cache, index=False)
        return result


# ----------------------------------------------------------------- NDVI: NASA AppEEARS
class AppEEARSClient:
    """Descarga NDVI MOD13Q1 (250 m, 16 días) por punto con NASA AppEEARS."""

    def __init__(
        self,
        *,
        token: str | None = None,
        user: str | None = None,
        password: str | None = None,
        cache_dir: Path | None = None,
        poll_seconds: int = 30,
        timeout_seconds: int = 7200,
    ) -> None:
        settings = get_settings()
        self.token = token or settings.earthdata_token
        self.user = user or settings.earthdata_user
        self.password = password or settings.earthdata_password
        self.cache_dir = Path(cache_dir or settings.cache_dir)
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._resolved_token: str | None = None

    # ------------------------------------------------------------------ auth
    def _get_token(self) -> str | None:
        if self._resolved_token:
            return self._resolved_token
        if self.token:
            self._resolved_token = self.token
            return self._resolved_token
        if not (self.user and self.password):
            logger.warning("AppEEARS: sin EARTHDATA_TOKEN ni usuario/clave; se omite NDVI")
            return None
        encoded = base64.b64encode(f"{self.user}:{self.password}".encode("utf-8")).decode("ascii")
        response = _request(
            "POST", f"{APPEEARS_BASE}/login", headers={"Authorization": f"Basic {encoded}"}, timeout=60.0
        )
        self._resolved_token = response.json().get("token")
        return self._resolved_token

    def _headers(self) -> dict[str, str]:
        token = self._get_token()
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ------------------------------------------------------------------ task
    def fetch_ndvi(
        self,
        cells: pd.DataFrame,
        start: str,
        end: str,
        *,
        refresh: bool = False,
        chunk_size: int = 500,
    ) -> pd.DataFrame:
        """Devuelve ``cell_id``, ``composite_date``, ``ndvi``, ``ndvi_quality``.

        Si no hay credenciales o una tarea falla, devuelve un DataFrame vacío y
        registra una advertencia; el pipeline continúa sin NDVI.
        """
        if cells.empty:
            return _empty_ndvi()
        if not self._get_token():
            return _empty_ndvi()

        cache = _cache_file(
            self.cache_dir,
            "ndvi",
            _hash_key({"cells": sorted(cells["cell_id"].tolist()), "start": start, "end": end, "v": 1}),
        )
        if cache.exists() and not refresh:
            return pd.read_parquet(cache)

        pieces: list[pd.DataFrame] = []
        for offset in range(0, len(cells), chunk_size):
            chunk = cells.iloc[offset : offset + chunk_size].reset_index(drop=True)
            chunk_key = _hash_key(
                {"cells": sorted(chunk["cell_id"].tolist()), "start": start, "end": end, "v": 1}
            )
            chunk_cache = _cache_file(self.cache_dir, "ndvi/chunks", chunk_key)
            if chunk_cache.exists() and not refresh:
                pieces.append(pd.read_parquet(chunk_cache))
                continue
            try:
                task_id = self._submit(chunk, start, end)
                if not task_id:
                    continue
                self._wait(task_id)
                frame = self._download(task_id, chunk)
                if not frame.empty:
                    frame.to_parquet(chunk_cache, index=False)  # reanudable por bloque
                    pieces.append(frame)
            except Exception as exc:  # noqa: BLE001 - una tarea no debe romper el dataset
                logger.warning("AppEEARS: tarea NDVI falló (%s); se continúa sin esos datos", exc)

        if not pieces:
            return _empty_ndvi()
        result = pd.concat(pieces, ignore_index=True).drop_duplicates(["cell_id", "composite_date"])
        result.to_parquet(cache, index=False)
        return result

    def _submit(self, cells: pd.DataFrame, start: str, end: str) -> str | None:
        payload = {
            "task_type": "point",
            "task_name": f"fuegoclaro_ndvi_{int(time.time())}",
            "params": {
                "dates": [{"startDate": _us_date(start), "endDate": _us_date(end)}],
                "layers": [
                    {"product": "MOD13Q1.061", "layer": "250m_16_days_NDVI"},
                    {"product": "MOD13Q1.061", "layer": "250m_16_days_pixel_reliability"},
                ],
                "coordinates": [
                    {
                        "id": str(row.cell_id),
                        "latitude": float(row.lat),
                        "longitude": float(row.lon),
                    }
                    for row in cells.itertuples(index=False)
                ],
                "output": {"format": {"type": "csv"}, "projection": "geographic"},
            },
        }
        response = _request("POST", f"{APPEEARS_BASE}/task", json=payload, headers=self._headers(), timeout=120.0)
        task_id = response.json().get("task_id")
        logger.info("AppEEARS: tarea %s enviada (%s celdas)", task_id, len(cells))
        return task_id

    def _wait(self, task_id: str) -> None:
        deadline = time.time() + self.timeout_seconds
        while time.time() < deadline:
            response = _request("GET", f"{APPEEARS_BASE}/task/{task_id}", headers=self._headers(), timeout=60.0)
            status = str(response.json().get("status", "")).lower()
            if status in {"done", "completed"}:
                return
            if status in {"error", "failed", "deleted"}:
                raise RuntimeError(f"AppEEARS task {task_id} terminó con estado {status}")
            time.sleep(self.poll_seconds)
        raise TimeoutError(f"AppEEARS task {task_id} excedió {self.timeout_seconds}s")

    def _download(self, task_id: str, cells: pd.DataFrame) -> pd.DataFrame:
        response = _request("GET", f"{APPEEARS_BASE}/bundle/{task_id}", headers=self._headers(), timeout=300.0)
        frames: list[pd.DataFrame] = []
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            for name in archive.namelist():
                if not name.lower().endswith(".csv"):
                    continue
                with archive.open(name) as handle:
                    frame = pd.read_csv(handle, low_memory=False)
                parsed = _parse_ndvi_csv(frame)
                if not parsed.empty:
                    frames.append(parsed)
        if not frames:
            return _empty_ndvi()
        result = pd.concat(frames, ignore_index=True)
        result["cell_id"] = result["cell_id"].astype(str)
        valid = set(cells["cell_id"].astype(str))
        return result[result["cell_id"].isin(valid)].reset_index(drop=True)


def _parse_ndvi_csv(frame: pd.DataFrame) -> pd.DataFrame:
    columns = list(frame.columns)
    id_column = next((c for c in columns if c.strip().lower() == "id"), None)
    date_column = next((c for c in columns if c.strip().lower() == "date"), None)
    if id_column is None or date_column is None:
        return _empty_ndvi()
    ndvi_column = next(
        (c for c in columns if "ndvi" in c.lower() and "reliability" not in c.lower() and "quality" not in c.lower()),
        None,
    )
    if ndvi_column is None:
        return _empty_ndvi()
    quality_column = next(
        (c for c in columns if "reliability" in c.lower() or "quality" in c.lower()),
        None,
    )
    result = pd.DataFrame(
        {
            "cell_id": frame[id_column].astype(str),
            "composite_date": pd.to_datetime(frame[date_column], errors="coerce").dt.normalize(),
            "ndvi": pd.to_numeric(frame[ndvi_column], errors="coerce") * 0.0001,
        }
    )
    if quality_column:
        result["ndvi_quality"] = pd.to_numeric(frame[quality_column], errors="coerce")
    else:
        result["ndvi_quality"] = np.nan
    # Los valores < -0.2 son relleno del producto (p. ej. -3000).
    result.loc[result["ndvi"] < -0.2, "ndvi"] = np.nan
    result.loc[result["ndvi_quality"] > 1, "ndvi"] = np.nan
    return result.dropna(subset=["composite_date"]).reset_index(drop=True)


def _empty_ndvi() -> pd.DataFrame:
    return pd.DataFrame(columns=["cell_id", "composite_date", "ndvi", "ndvi_quality"])


def _us_date(value: str) -> str:
    """``YYYY-MM-DD`` -> ``MM-DD-YYYY`` (formato de AppEEARS)."""
    return pd.Timestamp(value).strftime("%m-%d-%Y")


def ndvi_to_daily(ndvi: pd.DataFrame, cells: pd.DataFrame, dates: Iterable[pd.Timestamp]) -> pd.DataFrame:
    """Convierte compuestos NDVI a una serie diaria por celda.

    Para cada celda se hace forward-fill del último compuesto disponible y se
    conserva la antigüedad del dato. El cruce posterior con el panel usa
    ``date - 1 día`` para no filtrar información del día objetivo.
    """
    dates = pd.DatetimeIndex(sorted(pd.to_datetime(list(dates)).unique()))
    if ndvi.empty:
        return pd.DataFrame(
            {"cell_id": [], "date": [], "ndvi": [], "ndvi_quality": [], "ndvi_age_days": []}
        )
    frames: list[pd.DataFrame] = []
    for cell in cells["cell_id"].astype(str).unique():
        series = ndvi[ndvi["cell_id"].astype(str) == cell].sort_values("composite_date")
        if series.empty:
            continue
        source = series.set_index("composite_date")[["ndvi", "ndvi_quality"]]
        daily = source.reindex(dates, method="ffill")
        daily.index.name = "date"
        age = (dates - daily.index).days
        daily["ndvi_age_days"] = np.where(daily["ndvi"].isna(), np.nan, age)
        daily["cell_id"] = cell
        daily = daily.reset_index()
        frames.append(daily)
    if not frames:
        return pd.DataFrame(
            {"cell_id": [], "date": [], "ndvi": [], "ndvi_quality": [], "ndvi_age_days": []}
        )
    return pd.concat(frames, ignore_index=True)