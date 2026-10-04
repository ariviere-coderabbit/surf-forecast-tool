"""Open-Meteo Marine API — best-effort modeled sea surface height.

Open-Meteo's marine API does not expose a dedicated tidal-elevation variable.
This adapter attempts to retrieve sea_surface_height_above_sea_level if it
ever becomes available, and returns None with an appropriate notice otherwise.

All values carry the label: "Modeled sea level, not a tide table."
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings
from app.models import SeaLevelMeasurement

_MARINE_URL = "https://marine-api.open-meteo.com/v1/marine"
# Variable name to attempt; as of 2024 this is not in the public API.
_SL_VAR = "sea_surface_height_above_mean_sea_level"
_NOTE = "Modeled sea level, not a tide table."


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


async def fetch_sea_level(lat: float, lon: float) -> list[SeaLevelMeasurement]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": _SL_VAR,
        "models": settings.open_meteo_wave_model,
        "timeformat": "iso8601",
        "timezone": "UTC",
    }
    try:
        async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
            resp = await client.get(_MARINE_URL, params=params)
            if resp.status_code >= 400:
                # Variable unsupported — return empty list gracefully
                return []
    except httpx.HTTPError:
        return []

    data = resp.json()
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    heights = hourly.get(_SL_VAR, [])

    if not heights:
        return []

    measurements: list[SeaLevelMeasurement] = []
    for i, ts_str in enumerate(times):
        h = heights[i] if i < len(heights) else None
        measurements.append(
            SeaLevelMeasurement(
                timestamp=_parse_ts(ts_str),
                provider="open-meteo",
                model=settings.open_meteo_wave_model,
                height_m=float(h) if h is not None else None,
                note=_NOTE,
            )
        )
    return measurements
