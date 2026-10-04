"""Open-Meteo Marine API adapter — ICON-Wave (non-GFS) model.

Verified fields from https://open-meteo.com/en/docs/marine-weather-api (2024):
  wave_height, wave_direction, wave_period,
  wind_wave_height, wind_wave_direction, wind_wave_period,
  swell_wave_height, swell_wave_direction, swell_wave_period

Period statistics: wave_period is the dominant wave period (peak period proxy).
Directions are "from" in degrees true.
Units returned: m, s, degrees — no conversion needed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings
from app.models import WaveMeasurement

_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"

_HOURLY_VARS = [
    "wave_height",
    "wave_direction",
    "wave_period",
    "wind_wave_height",
    "wind_wave_direction",
    "wind_wave_period",
    "swell_wave_height",
    "swell_wave_direction",
    "swell_wave_period",
]


def _parse_ts(s: str) -> datetime:
    """Parse an ISO timestamp and replace its timezone with UTC without conversion.

    Raise ValueError for an invalid timestamp string.
    """
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


async def fetch_waves(lat: float, lon: float) -> list[WaveMeasurement]:
    """Fetch hourly waves from the configured model for coordinates in degrees.

    Return UTC measurements with heights in meters, periods in seconds,
    and directions in degrees, plus grid coordinates and sampling distance
    in kilometers when available. Missing field values remain None; absent
    timestamps yield an empty list. HTTP, JSON decoding, timestamp or numeric
    conversion, and model validation errors propagate.
    """
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY_VARS),
        "models": settings.open_meteo_wave_model,
        "wind_speed_unit": "ms",
        "timeformat": "iso8601",
        "timezone": "UTC",
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(_MARINE_URL, params=params)
        resp.raise_for_status()

    data = resp.json()
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    # Grid point actually used by Open-Meteo
    grid_lat: Optional[float] = data.get("latitude")
    grid_lon: Optional[float] = data.get("longitude")
    sampling_km: Optional[float] = None
    if grid_lat is not None and grid_lon is not None:
        sampling_km = _haversine_km(lat, lon, grid_lat, grid_lon)

    measurements: list[WaveMeasurement] = []
    for i, ts_str in enumerate(times):
        def _v(key: str) -> Optional[float]:
            """Return this hour's numeric field, or None if absent or null.

            Invalid numeric values raise TypeError or ValueError.
            """
            vals = hourly.get(key, [])
            if i < len(vals):
                v = vals[i]
                return float(v) if v is not None else None
            return None

        measurements.append(
            WaveMeasurement(
                timestamp=_parse_ts(ts_str),
                provider="open-meteo",
                model=settings.open_meteo_wave_model,
                wave_height_m=_v("wave_height"),
                wave_period_s=_v("wave_period"),
                wave_direction_deg=_v("wave_direction"),
                wind_wave_height_m=_v("wind_wave_height"),
                wind_wave_period_s=_v("wind_wave_period"),
                wind_wave_direction_deg=_v("wind_wave_direction"),
                swell_height_m=_v("swell_wave_height"),
                swell_period_s=_v("swell_wave_period"),
                swell_direction_deg=_v("swell_wave_direction"),
                grid_lat=grid_lat,
                grid_lon=grid_lon,
                sampling_distance_km=sampling_km,
            )
        )
    return measurements


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometers for coordinates in degrees."""
    import math
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
