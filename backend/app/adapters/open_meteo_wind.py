"""Open-Meteo Forecast API adapter for surface wind.

Verified fields from https://open-meteo.com/en/docs (2024):
  wind_speed_10m (m/s), wind_direction_10m (degrees from, true),
  wind_gusts_10m (m/s)

Default model is best_match (Open-Meteo selects optimal model per location).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import httpx

from app.config import settings
from app.models import WindMeasurement

_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

_HOURLY_VARS = [
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]

_WIND_MODEL = "best_match"


def _parse_ts(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


async def fetch_wind(lat: float, lon: float) -> list[WindMeasurement]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(_HOURLY_VARS),
        "models": _WIND_MODEL,
        "wind_speed_unit": "ms",
        "timeformat": "iso8601",
        "timezone": "UTC",
        "forecast_days": 7,
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(_FORECAST_URL, params=params)
        resp.raise_for_status()

    data = resp.json()
    hourly = data.get("hourly", {})
    times = hourly.get("time", [])

    grid_lat: Optional[float] = data.get("latitude")
    grid_lon: Optional[float] = data.get("longitude")

    measurements: list[WindMeasurement] = []
    for i, ts_str in enumerate(times):
        def _v(key: str) -> Optional[float]:
            vals = hourly.get(key, [])
            if i < len(vals):
                v = vals[i]
                return float(v) if v is not None else None
            return None

        measurements.append(
            WindMeasurement(
                timestamp=_parse_ts(ts_str),
                provider="open-meteo",
                model=_WIND_MODEL,
                speed_mps=_v("wind_speed_10m"),
                direction_deg=_v("wind_direction_10m"),
                gust_mps=_v("wind_gusts_10m"),
            )
        )
    return measurements
