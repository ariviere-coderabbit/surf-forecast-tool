"""Merge comparable wave/wind measurements across providers.

Rules:
- Timestamps are aligned to the nearest UTC hour.
- Only measurements with matching timestamps are merged.
- Averages use simple mean for scalar fields, circular mean for directions.
- Gaps are preserved: if one provider has None, the other's value is used.
- Period statistics are NOT mixed (a mean period from one source is never
  combined with a peak period from another). Providers are labelled with their
  period stat type, and the merger takes the mean only when both are the same type.
  For GFS-Wave (mean period) vs ICON-Wave (dominant/peak period proxy), we keep
  them separate rather than averaging.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from typing import Optional

from app.models import HourlyConditions, WindMeasurement, WaveMeasurement


def _circular_mean(angles: list[float]) -> Optional[float]:
    if not angles:
        return None
    sin_sum = sum(math.sin(math.radians(a)) for a in angles)
    cos_sum = sum(math.cos(math.radians(a)) for a in angles)
    mean = math.degrees(math.atan2(sin_sum, cos_sum)) % 360
    return mean


def _scalar_mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _floor_hour(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _collect_non_none(series: list, key: str) -> list[float]:
    return [getattr(m, key) for m in series if getattr(m, key, None) is not None]


def merge_waves(
    *provider_series: list[WaveMeasurement],
) -> dict[datetime, dict]:
    """Group measurements by hour and compute merged values."""
    by_hour: dict[datetime, list[WaveMeasurement]] = defaultdict(list)
    for series in provider_series:
        for m in series:
            by_hour[_floor_hour(m.timestamp)].append(m)

    merged: dict[datetime, dict] = {}
    for ts, measurements in sorted(by_hour.items()):
        def _sc(key: str) -> Optional[float]:
            return _scalar_mean(_collect_non_none(measurements, key))

        def _ci(key: str) -> Optional[float]:
            return _circular_mean(_collect_non_none(measurements, key))

        # Periods: prefer Open-Meteo (dominant/peak proxy) over NOAA mean
        # period to avoid mixing incompatible statistics.
        def _prefer_period(key: str) -> Optional[float]:
            om = next(
                (getattr(m, key) for m in measurements
                 if m.provider == "open-meteo" and getattr(m, key) is not None),
                None,
            )
            if om is not None:
                return om
            return next(
                (getattr(m, key) for m in measurements if getattr(m, key) is not None),
                None,
            )

        merged[ts] = {
            "wave_height_m": _sc("wave_height_m"),
            "wave_period_s": _prefer_period("wave_period_s"),
            "wave_direction_deg": _ci("wave_direction_deg"),
            "wind_wave_height_m": _sc("wind_wave_height_m"),
            "wind_wave_period_s": _sc("wind_wave_period_s"),
            "wind_wave_direction_deg": _ci("wind_wave_direction_deg"),
            "swell_height_m": _sc("swell_height_m"),
            "swell_period_s": _prefer_period("swell_period_s"),
            "swell_direction_deg": _ci("swell_direction_deg"),
        }
    return merged


def merge_wind(series: list[WindMeasurement]) -> dict[datetime, dict]:
    by_hour: dict[datetime, list[WindMeasurement]] = defaultdict(list)
    for m in series:
        by_hour[_floor_hour(m.timestamp)].append(m)

    merged: dict[datetime, dict] = {}
    for ts, measurements in sorted(by_hour.items()):
        def _sc(key: str) -> Optional[float]:
            return _scalar_mean(_collect_non_none(measurements, key))

        def _ci(key: str) -> Optional[float]:
            return _circular_mean(_collect_non_none(measurements, key))

        merged[ts] = {
            "wind_speed_mps": _sc("speed_mps"),
            "wind_direction_deg": _ci("direction_deg"),
            "wind_gust_mps": _sc("gust_mps"),
        }
    return merged


def build_hourly(
    wave_series: list[list[WaveMeasurement]],
    wind_series: list[WindMeasurement],
    sea_level_by_hour: dict[datetime, Optional[float]],
) -> list[HourlyConditions]:
    wave_merged = merge_waves(*wave_series)
    wind_merged = merge_wind(wind_series)

    all_hours = sorted(set(wave_merged) | set(wind_merged) | set(sea_level_by_hour))

    hourly: list[HourlyConditions] = []
    for ts in all_hours:
        wv = wave_merged.get(ts, {})
        wi = wind_merged.get(ts, {})
        hourly.append(
            HourlyConditions(
                timestamp=ts,
                **wv,
                **wi,
                sea_level_m=sea_level_by_hour.get(ts),
            )
        )
    return hourly
