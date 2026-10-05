"""FastAPI application — surf forecast tool backend."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from datetime import timezone as tz

import httpx
from fastapi import HTTPException

from app.adapters import open_meteo_waves, open_meteo_wind, open_meteo_sealevel, noaa_gfswave
from app.cache import forecast_cache
from app.config import settings
from app.merger import build_hourly, _floor_hour
from app.models import (
    ForecastResponse,
    GeoCandidate,
    ProviderHourly,
    ProviderSeries,
)
from app.scorer import best_window, score_all
from app.spot_profiles import get_profile

log = logging.getLogger(__name__)


async def get_forecast(
    lat: float, lon: float, timezone: str = "UTC", name: str = "",
    country: str = "", country_code: str = "",
) -> ForecastResponse:
    cache_key = f"forecast|{lat:.4f}|{lon:.4f}|{timezone}|{name}|{country}"
    cached = forecast_cache.get(cache_key)
    if cached:
        return ForecastResponse(**cached)

    location = GeoCandidate(
        id=0,
        name=name or f"{lat:.4f},{lon:.4f}",
        country=country,
        country_code=country_code,
        latitude=lat,
        longitude=lon,
        timezone=timezone,
    )
    profile = get_profile(lat, lon)
    errors: list[str] = []
    warnings: list[str] = []
    provider_series: list[ProviderSeries] = []

    # --- Fetch wave data ---
    wave_sources: list[list] = []

    # Open-Meteo (DWD GWAM)
    try:
        om_waves = await open_meteo_waves.fetch_waves(lat, lon)
        wave_sources.append(om_waves)
        provider_series.append(
            ProviderSeries(
                provider="open-meteo",
                model=settings.open_meteo_wave_model,
                status="ok",
                hourly=_wave_to_provider(om_waves),
            )
        )
    except Exception as exc:
        errors.append(f"Open-Meteo waves: {exc}")
        provider_series.append(
            ProviderSeries(provider="open-meteo", model=settings.open_meteo_wave_model, status="error", error=str(exc))
        )

    # NOAA GFS-Wave (from disk cache)
    noaa_waves = noaa_gfswave.load_measurements(lat, lon)
    if noaa_waves:
        wave_sources.append(noaa_waves)
        provider_series.append(
            ProviderSeries(
                provider="noaa-ncep",
                model="GFS-Wave-0.16",
                status="ok",
                hourly=_wave_to_provider(noaa_waves),
            )
        )
    else:
        warnings.append("NOAA GFS-Wave data not yet cached; background refresh scheduled.")
        asyncio.create_task(noaa_gfswave.maybe_refresh())

    if not wave_sources:
        raise HTTPException(
            status_code=503,
            detail="No swell data available — all wave providers failed.",
        )

    # --- Fetch wind data ---
    wind_series = []
    try:
        wind_series = await open_meteo_wind.fetch_wind(lat, lon)
        provider_series.append(
            ProviderSeries(
                provider="open-meteo",
                model="best_match",
                status="ok",
                hourly=_wind_to_provider(wind_series),
            )
        )
    except Exception as exc:
        errors.append(f"Open-Meteo wind: {exc}")
        provider_series.append(
            ProviderSeries(provider="open-meteo", model="best_match", status="error", error=str(exc))
        )

    # --- Sea level (best-effort) ---
    sea_level_by_hour = {}
    try:
        sl_data = await open_meteo_sealevel.fetch_sea_level(lat, lon)
        for m in sl_data:
            sea_level_by_hour[_floor_hour(m.timestamp)] = m.height_m
    except Exception:
        pass

    # --- Build merged hourly ---
    hourly = build_hourly(wave_sources, wind_series, sea_level_by_hour)
    hourly = score_all(hourly, profile)
    bw = best_window(hourly)

    notices = [
        "Surfability scores are approximate and uncalibrated heuristics.",
    ]
    if not profile.calibrated:
        notices.append(
            f"The '{profile.name}' profile is approximate and has not been field-calibrated."
        )
    if not sea_level_by_hour:
        notices.append("Sea level data unavailable from Open-Meteo for this location.")
    else:
        notices.append("Sea level is modeled, not a tide table.")

    response = ForecastResponse(
        location=location,
        spot_profile=profile,
        generated_at=datetime.now(tz.utc),
        hourly=hourly,
        providers=provider_series,
        best_window=bw,
        errors=errors,
        warnings=warnings,
        notices=notices,
    )

    # Only cache fully successful responses so provider errors or missing NOAA
    # data are not frozen in the cache for the full TTL.
    if not warnings and not errors:
        forecast_cache.set(cache_key, response.model_dump(mode="json"))
    return response


def _wave_to_provider(measurements) -> list[ProviderHourly]:
    return [
        ProviderHourly(
            timestamp=m.timestamp,
            wave_height_m=m.wave_height_m,
            wave_period_s=m.wave_period_s,
            wave_direction_deg=m.wave_direction_deg,
            swell_height_m=m.swell_height_m,
            swell_period_s=m.swell_period_s,
            grid_lat=m.grid_lat,
            grid_lon=m.grid_lon,
            sampling_distance_km=m.sampling_distance_km,
        )
        for m in measurements
    ]


def _wind_to_provider(measurements) -> list[ProviderHourly]:
    return [
        ProviderHourly(
            timestamp=m.timestamp,
            wind_speed_mps=m.speed_mps,
            wind_direction_deg=m.direction_deg,
        )
        for m in measurements
    ]
