"""Explainable condition similarity; never modifies surfability scores."""
import math

from app.config import settings
from app.journal_models import Comparison, SessionMatch, SurfSession
from app.models import HourlyConditions

REQUIRED = ("wave_height_m", "wave_period_s", "wind_speed_mps")


def has_required(conditions: HourlyConditions) -> bool:
    return all(getattr(conditions, field) is not None and math.isfinite(getattr(conditions, field)) for field in REQUIRED)


def find_matches(sessions: list[SurfSession], target: HourlyConditions) -> list[SessionMatch]:
    if not has_required(target):
        return []
    tolerances = {
        "wave_height_m": settings.match_height_m,
        "wave_period_s": settings.match_period_s,
        "wave_direction_deg": settings.match_direction_deg,
        "wind_speed_mps": settings.match_wind_mps,
        "wind_direction_deg": settings.match_direction_deg,
        "sea_level_m": settings.match_sea_level_m,
    }
    matches = []
    for session in sessions:
        comparisons = []
        for field, tolerance in tolerances.items():
            observed = getattr(session.observations, field, None)
            modeled = getattr(session.snapshot.conditions, field, None) if session.snapshot else None
            value = observed if observed is not None else modeled
            forecast_value = getattr(target, field)
            if value is None or forecast_value is None or not all(map(math.isfinite, [value, forecast_value])):
                continue
            difference = abs(value - forecast_value)
            if field.endswith("_deg"):
                difference = abs((value - forecast_value + 180) % 360 - 180)
            comparisons.append(Comparison(field=field, session_value=value, forecast_value=forecast_value,
                                          difference=difference, tolerance=tolerance,
                                          source="observed" if observed is not None else "modeled"))
        if not set(REQUIRED).issubset({c.field for c in comparisons}):
            continue
        if any(c.tolerance <= 0 or c.difference > c.tolerance + 1e-9 for c in comparisons):
            continue
        distance = sum(c.difference / c.tolerance for c in comparisons) / len(comparisons)
        matches.append(SessionMatch(session=session, distance=distance, comparisons=comparisons))
    return sorted(matches, key=lambda m: (m.distance, -m.session.session_at.timestamp(), m.session.id))[:3]
