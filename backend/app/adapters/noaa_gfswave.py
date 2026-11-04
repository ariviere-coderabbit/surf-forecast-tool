"""NOAA/NCEP GFS-Wave regional adapter.

Data source: NOMADS filter service for GFS-Wave global 0.16° GRIB2.
  https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl

Verified GRIB2 shortNames (NOAA GFS-Wave, as of 2024):
  HTSGW  – Significant height of combined wind waves and swell (m)
  PERPW  – Primary wave mean period (s)
  DIRPW  – Primary wave direction (degrees from)
  WVHGT  – Wind wave significant height (m)
  WVPER  – Wind wave mean period (s)
  WVDIR  – Wind wave direction (degrees from)
  SWELL  – Swell wave significant height (m)
  SWPER  – Swell wave mean period (s)
  SWDIR  – Swell wave direction (degrees from)

Period statistics: PERPW and SWPER are mean periods (not peak).

Background refresh runs every 6 h; requests are paced ≥10 s apart.
Decoded data is stored as JSON on disk in the noaa_data_dir.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import httpx

from app.config import settings
from app.models import WaveMeasurement

log = logging.getLogger(__name__)

_NOMADS_FILTER = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfswave.pl"
_MODEL = "GFS-Wave-0.16"

# GFS-Wave runs at 00, 06, 12, 18 UTC
_CYCLES = (0, 6, 12, 18)
# Forecast hours available (0–120 h at 3-h steps, then sparse)
_FHOURS = list(range(0, 121, 3))

_GRIB_VARS = [
    "HTSGW", "PERPW", "DIRPW",
    "WVHGT", "WVPER", "WVDIR",
    "SWELL", "SWPER", "SWDIR",
]

# Mapping from GRIB shortName to WaveMeasurement field
_FIELD_MAP = {
    "HTSGW": "wave_height_m",
    "PERPW": "wave_period_s",
    "DIRPW": "wave_direction_deg",
    "WVHGT": "wind_wave_height_m",
    "WVPER": "wind_wave_period_s",
    "WVDIR": "wind_wave_direction_deg",
    "SWELL": "swell_height_m",
    "SWPER": "swell_period_s",
    "SWDIR": "swell_direction_deg",
}

_last_refresh: Optional[float] = None
_running_task: Optional[asyncio.Task] = None
_refresh_lock = asyncio.Lock()


def _latest_cycle(now: datetime) -> tuple[str, str]:
    """Return (YYYYMMDD, HH) for the cycle at least five hours before UTC now.

    This estimates availability without checking whether the cycle is complete.
    """
    # GFS cycle data typically available ~4-5 h after init; use a 5 h lag
    lag_h = 5
    ref = now - timedelta(hours=lag_h)
    cycle_h = max(c for c in _CYCLES if c <= ref.hour)
    date_str = ref.strftime("%Y%m%d")
    hh = f"{cycle_h:02d}"
    return date_str, hh


def _cache_path(date_str: str, hh: str) -> Path:
    """Return the cache path for a cycle identified by YYYYMMDD and UTC HH."""
    return settings.noaa_data_dir / f"gfswave_{date_str}_{hh}.json"


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometers for coordinates in degrees."""
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _fetch_one_hour(
    client: httpx.AsyncClient,
    date_str: str,
    hh: str,
    fhour: int,
) -> Optional[dict]:
    """Fetch and decode a regional forecast at fhour hours after YYYYMMDD/HH UTC.

    Return a UTC valid time and field grids, or None for HTTP errors,
    non-200 responses, bodies shorter than 100 bytes, or no decoded fields.
    Errors not handled by the decoder propagate.
    """
    fname = f"gfswave.t{hh}z.global.0p16.f{fhour:03d}.grib2"
    params: dict[str, object] = {
        "file": fname,
        "subregion": "",
        "leftlon": settings.noaa_region_left_lon,
        "rightlon": settings.noaa_region_right_lon,
        "toplat": settings.noaa_region_top_lat,
        "bottomlat": settings.noaa_region_bottom_lat,
        "dir": f"/gfs.{date_str}/{hh}/atmos",
    }
    for v in _GRIB_VARS:
        params[f"var_{v}"] = "on"

    try:
        resp = await client.get(_NOMADS_FILTER, params=params, timeout=60.0)
        if resp.status_code != 200 or len(resp.content) < 100:
            return None
    except httpx.HTTPError as exc:
        log.warning("NOAA fetch error fhour=%d: %s", fhour, exc)
        return None

    return _decode_grib(resp.content, date_str, hh, fhour)


def _decode_grib(content: bytes, date_str: str, hh: str, fhour: int) -> Optional[dict]:
    """Return a UTC valid_time and field grids from a cycle's GRIB2 bytes.

    The cycle is YYYYMMDD/HH UTC; fhour is its forecast offset in hours.
    Each field contains parallel lats, lons, and vals lists, with missing
    values replaced by None. Return None if eccodes is unavailable or no
    requested fields were decoded. Handled ecCodes read errors may yield
    partial data; other decoding errors propagate. Invalid cycle dates
    raise ValueError when fields were decoded.
    """
    try:
        import eccodes  # type: ignore
    except ImportError:
        log.error("eccodes not installed; cannot decode NOAA GRIB2 data")
        return None

    import io

    fields: dict[str, dict] = {}
    stream = io.BytesIO(content)

    while True:
        try:
            msg = eccodes.codes_grib_new_from_file(stream)
        except eccodes.CodesInternalError:
            break
        if msg is None:
            break
        try:
            short_name = eccodes.codes_get(msg, "shortName")
            if short_name not in _GRIB_VARS:
                continue
            ni = eccodes.codes_get(msg, "Ni")
            nj = eccodes.codes_get(msg, "Nj")
            lats = eccodes.codes_get_array(msg, "latitudes")
            lons = eccodes.codes_get_array(msg, "longitudes")
            vals = eccodes.codes_get_array(msg, "values")
            missing = eccodes.codes_get(msg, "missingValue")
            fields[short_name] = {
                "lats": lats.tolist(),
                "lons": lons.tolist(),
                "vals": [None if abs(v - missing) < 1e-3 else float(v) for v in vals],
            }
        except eccodes.CodesInternalError:
            pass
        finally:
            eccodes.codes_release(msg)

    if not fields:
        return None

    base = datetime(
        int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8]),
        int(hh), 0, 0, tzinfo=timezone.utc
    )
    valid_time = base + timedelta(hours=fhour)
    return {
        "valid_time": valid_time.isoformat(),
        "fields": fields,
    }


async def _refresh_cycle(date_str: str, hh: str) -> None:
    """Fetch a cycle's regional forecasts and save available hours to disk.

    Pace requests using the configured delay in seconds. Update the refresh
    time only after writing nonempty results; leave an existing file alone
    if no hours are retrieved. Always clear the running-task reference.
    Unhandled fetch, decoding, and file-write errors propagate.
    """
    global _last_refresh, _running_task
    log.info("Refreshing NOAA GFS-Wave cycle %s/%s", date_str, hh)
    path = _cache_path(date_str, hh)
    hours_data: list[dict] = []

    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            for fhour in _FHOURS:
                result = await _fetch_one_hour(client, date_str, hh, fhour)
                if result is not None:
                    hours_data.append(result)
                await asyncio.sleep(settings.noaa_request_pace)

        if hours_data:
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(hours_data))
            temporary.replace(path)
            log.info("Saved %d NOAA forecast hours to %s", len(hours_data), path)
            _last_refresh = time.monotonic()
        else:
            log.warning("No NOAA data retrieved for cycle %s/%s — will retry next call", date_str, hh)
    finally:
        _running_task = None


async def maybe_refresh(*, force: bool = False) -> None:
    """Schedule a NOAA refresh if none is running and the freshness check expires.

    Use elapsed seconds since the last successful in-process refresh, or
    otherwise the selected cycle cache's modification time. A fresh timestamp
    suppresses refresh only when the expected cycle file exists. Force bypasses
    this throttle for missing/unusable data, but never starts a duplicate task.
    Return without waiting for the download; filesystem stat errors propagate.
    """
    global _running_task
    async with _refresh_lock:
        if _running_task is not None and not _running_task.done():
            return

        now = datetime.now(timezone.utc)
        date_str, hh = _latest_cycle(now)
        path = _cache_path(date_str, hh)

        # In-process: honour TTL from the last successful refresh.
        if not force and path.exists() and _last_refresh is not None:
            if (time.monotonic() - _last_refresh) < settings.noaa_refresh_interval:
                return
        else:
            # Post-restart: use the cache file's mtime so a stale file that
            # survived a process restart still triggers a refresh.
            if not force and path.exists():
                age = time.time() - path.stat().st_mtime
                if age < settings.noaa_refresh_interval:
                    return

        _running_task = asyncio.create_task(_refresh_cycle(date_str, hh))


def _nearest_point(
    lats: list[float], lons: list[float], vals: list[Optional[float]],
    target_lat: float, target_lon: float,
) -> tuple[Optional[float], float, float]:
    """Return (value, grid_lat, grid_lon) for the nearest non-missing grid point.

    Coordinates are in degrees. Consider aligned entries up to the shortest
    list and keep the first point in a distance tie. If no value is present,
    return (None, target_lat, target_lon).
    """
    best_val: Optional[float] = None
    best_dist = float("inf")
    best_lat = target_lat
    best_lon = target_lon

    for i, (la, lo, va) in enumerate(zip(lats, lons, vals)):
        if va is None:
            continue
        d = _haversine_km(target_lat, target_lon, la, lo)
        if d < best_dist:
            best_dist = d
            best_val = va
            best_lat = la
            best_lon = lo

    return best_val, best_lat, best_lon


def load_measurements(
    lat: float, lon: float, *, now: Optional[datetime] = None,
) -> list[WaveMeasurement]:
    """Use the newest usable cycle within the age limit, measured from issue time.

    Never use cycles newer than the expected published cycle. Skip corrupt,
    empty, expired, and past-only snapshots. Forecast valid time is distinct
    from cycle issue time: a future prediction can still come from an old run.
    """
    now = now or datetime.now(timezone.utc)
    date_str, hh = _latest_cycle(now)
    latest = datetime.strptime(date_str + hh, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    cycle = latest
    while (now - cycle).total_seconds() <= settings.noaa_max_cycle_age_hours * 3600:
        path = _cache_path(cycle.strftime("%Y%m%d"), cycle.strftime("%H"))
        try:
            hours_data = json.loads(path.read_text())
            measurements = _extract_measurements(hours_data, lat, lon, now)
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            measurements = []
        if measurements:
            return [m.model_copy(update={
                "forecast_cycle": cycle,
                "is_fallback": cycle != latest,
            }) for m in measurements]
        cycle -= timedelta(hours=6)
    return []


def _extract_measurements(hours_data, lat, lon, now) -> list[WaveMeasurement]:
    """Decode one snapshot; malformed snapshots are rejected by the caller."""
    if not isinstance(hours_data, list):
        raise ValueError("NOAA snapshot must contain a list of hours")
    measurements: list[WaveMeasurement] = []
    for hour in hours_data:
        valid_time = datetime.fromisoformat(hour["valid_time"])
        if valid_time.tzinfo is None:
            raise ValueError("NOAA valid time must include a timezone")
        if valid_time < now.replace(minute=0, second=0, microsecond=0):
            continue
        fields: dict[str, dict] = hour.get("fields", {})

        kwargs: dict = {
            "timestamp": valid_time,
            "provider": "noaa-ncep",
            "model": _MODEL,
        }

        grid_lat: Optional[float] = None
        grid_lon: Optional[float] = None

        for short_name, field_name in _FIELD_MAP.items():
            if short_name not in fields:
                continue
            fd = fields[short_name]
            val, glat, glon = _nearest_point(
                fd["lats"], fd["lons"], fd["vals"], lat, lon
            )
            kwargs[field_name] = val
            if grid_lat is None:
                grid_lat = glat
                grid_lon = glon

        if grid_lat is not None:
            kwargs["grid_lat"] = grid_lat
            kwargs["grid_lon"] = grid_lon
            kwargs["sampling_distance_km"] = _haversine_km(lat, lon, grid_lat, grid_lon)

        measurement = WaveMeasurement(**kwargs)
        if measurement.wave_height_m is not None or measurement.swell_height_m is not None:
            measurements.append(measurement)

    return measurements
