"""Spot profiles for surfability scoring.

The Jacó profile is approximate and explicitly uncalibrated.
All other locations receive the generic fallback profile.
"""
from __future__ import annotations

import math
from app.models import SpotProfile

# Jacó faces southwest (~220°). Works best with south-to-southwest swells.
_JACO = SpotProfile(
    name="Jacó",
    latitude=9.613,
    longitude=-84.628,
    ideal_swell_direction_deg=200.0,   # swell coming from SSW
    ideal_swell_direction_tolerance_deg=50.0,
    ideal_wave_height_min_m=0.5,
    ideal_wave_height_max_m=2.0,
    ideal_period_min_s=8.0,
    ideal_wind_direction_deg=60.0,     # offshore = easterly/NE
    ideal_wind_direction_tolerance_deg=60.0,
    max_wind_speed_mps=8.0,
    calibrated=False,
)

_GENERIC = SpotProfile(
    name="Generic",
    latitude=0.0,
    longitude=0.0,
    ideal_swell_direction_deg=None,
    ideal_swell_direction_tolerance_deg=90.0,
    ideal_wave_height_min_m=0.4,
    ideal_wave_height_max_m=2.5,
    ideal_period_min_s=7.0,
    ideal_wind_direction_deg=None,
    ideal_wind_direction_tolerance_deg=90.0,
    max_wind_speed_mps=10.0,
    calibrated=False,
)

# Match radius (km) to use the named profile
_MATCH_RADIUS_KM = 15.0

_NAMED_PROFILES: list[SpotProfile] = [_JACO]


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_profile(lat: float, lon: float) -> SpotProfile:
    for profile in _NAMED_PROFILES:
        if _haversine_km(lat, lon, profile.latitude, profile.longitude) <= _MATCH_RADIUS_KM:
            return profile.model_copy(update={"latitude": lat, "longitude": lon})
    return _GENERIC.model_copy(update={"name": "Generic", "latitude": lat, "longitude": lon})
