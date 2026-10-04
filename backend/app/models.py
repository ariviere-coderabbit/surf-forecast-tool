"""Pydantic models for all API request/response and internal data types."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------

class GeoCandidate(BaseModel):
    id: int
    name: str
    country: str
    country_code: str
    admin1: Optional[str] = None
    latitude: float
    longitude: float
    timezone: str
    population: Optional[int] = None


class GeocodeResponse(BaseModel):
    query: str
    candidates: list[GeoCandidate]
    selected: Optional[GeoCandidate] = None


# ---------------------------------------------------------------------------
# Raw provider measurements (normalised to SI)
# ---------------------------------------------------------------------------

class WaveMeasurement(BaseModel):
    """Single combined + component wave measurement from one provider."""
    timestamp: datetime                        # UTC
    provider: str
    model: str

    # Combined
    wave_height_m: Optional[float] = None      # Hs, m
    wave_period_s: Optional[float] = None      # peak or mean period, s
    wave_direction_deg: Optional[float] = None  # from, degrees true

    # Wind-wave component
    wind_wave_height_m: Optional[float] = None
    wind_wave_period_s: Optional[float] = None
    wind_wave_direction_deg: Optional[float] = None

    # Swell component
    swell_height_m: Optional[float] = None
    swell_period_s: Optional[float] = None
    swell_direction_deg: Optional[float] = None

    # Grid provenance
    grid_lat: Optional[float] = None
    grid_lon: Optional[float] = None
    sampling_distance_km: Optional[float] = None


class WindMeasurement(BaseModel):
    """Single wind measurement from one provider."""
    timestamp: datetime                        # UTC
    provider: str
    model: str

    speed_mps: Optional[float] = None         # m/s
    direction_deg: Optional[float] = None     # from, degrees true
    gust_mps: Optional[float] = None


class SeaLevelMeasurement(BaseModel):
    """Modeled sea surface height — NOT a tidal prediction."""
    timestamp: datetime                        # UTC
    provider: str
    model: str
    height_m: Optional[float] = None
    note: str = "Modeled sea level, not a tide table."


# ---------------------------------------------------------------------------
# Merged hourly forecast point
# ---------------------------------------------------------------------------

class HourlyConditions(BaseModel):
    timestamp: datetime

    # Waves (merged)
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    wave_direction_deg: Optional[float] = None
    wind_wave_height_m: Optional[float] = None
    wind_wave_period_s: Optional[float] = None
    wind_wave_direction_deg: Optional[float] = None
    swell_height_m: Optional[float] = None
    swell_period_s: Optional[float] = None
    swell_direction_deg: Optional[float] = None

    # Wind (merged)
    wind_speed_mps: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    wind_gust_mps: Optional[float] = None

    # Sea level
    sea_level_m: Optional[float] = None

    # Surfability
    score: Optional[float] = None             # 0–10
    confidence: Optional[float] = None        # 0–1

    # Component breakdown
    score_wave_height: Optional[float] = None
    score_wave_period: Optional[float] = None
    score_wind: Optional[float] = None
    score_direction: Optional[float] = None


# ---------------------------------------------------------------------------
# Provider comparison (raw values, unmerged)
# ---------------------------------------------------------------------------

class ProviderHourly(BaseModel):
    timestamp: datetime
    wave_height_m: Optional[float] = None
    wave_period_s: Optional[float] = None
    wave_direction_deg: Optional[float] = None
    swell_height_m: Optional[float] = None
    swell_period_s: Optional[float] = None
    wind_speed_mps: Optional[float] = None
    wind_direction_deg: Optional[float] = None
    grid_lat: Optional[float] = None
    grid_lon: Optional[float] = None
    sampling_distance_km: Optional[float] = None


class ProviderSeries(BaseModel):
    provider: str
    model: str
    status: str                               # "ok" | "error" | "partial"
    error: Optional[str] = None
    hourly: list[ProviderHourly] = []


# ---------------------------------------------------------------------------
# Best surfing window
# ---------------------------------------------------------------------------

class BestWindow(BaseModel):
    start: datetime
    end: datetime
    mean_score: float
    peak_score: float


# ---------------------------------------------------------------------------
# Forecast response
# ---------------------------------------------------------------------------

class SpotProfile(BaseModel):
    name: str
    latitude: float
    longitude: float
    ideal_swell_direction_deg: Optional[float] = None
    ideal_swell_direction_tolerance_deg: float = 45.0
    ideal_wave_height_min_m: float = 0.5
    ideal_wave_height_max_m: float = 2.5
    ideal_period_min_s: float = 8.0
    ideal_wind_direction_deg: Optional[float] = None
    ideal_wind_direction_tolerance_deg: float = 45.0
    max_wind_speed_mps: float = 10.0
    calibrated: bool = False


class ForecastResponse(BaseModel):
    location: GeoCandidate
    spot_profile: SpotProfile
    generated_at: datetime
    hourly: list[HourlyConditions]
    providers: list[ProviderSeries]
    best_window: Optional[BestWindow] = None
    errors: list[str] = []
    warnings: list[str] = []
    notices: list[str] = [
        "Surfability scores are approximate and uncalibrated heuristics.",
        "Sea level is modeled, not a tide table.",
    ]
