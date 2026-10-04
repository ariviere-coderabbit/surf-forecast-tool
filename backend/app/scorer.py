"""Surfability scorer.

Produces a 0–10 score and a 0–1 confidence per hourly slot.
Scores are heuristic, explicitly uncalibrated, and profile-specific.

Component weights sum to 1.0:
  wave_height  0.35
  wave_period  0.25
  wind         0.25
  direction    0.15
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Optional

from app.models import BestWindow, HourlyConditions, SpotProfile


_W_HEIGHT = 0.35
_W_PERIOD = 0.25
_W_WIND = 0.25
_W_DIR = 0.15


def _direction_score(direction: float, ideal: float, tolerance: float) -> float:
    """1.0 when on ideal, decreasing to 0.0 at ±tolerance degrees."""
    diff = abs((direction - ideal + 180) % 360 - 180)
    if diff >= tolerance:
        return 0.0
    return 1.0 - diff / tolerance


def _height_score(height_m: float, min_m: float, max_m: float) -> float:
    """Score height in meters with a flat 1.0 from min_m through max_m.

    Below min_m, return height_m / min_m when min_m is positive, otherwise
    zero. Above max_m, decay to zero over max(max_m - min_m, max_m) meters;
    a zero decay scale raises ZeroDivisionError.
    """
    # Trapezoid: ramp up to min_m, flat 1.0 through max_m, then decay.
    # This avoids the discontinuity of a peaked-midpoint formula and uses
    # ideal_range as the decay scale so large max_m values still penalise
    # significantly oversized surf.
    if height_m < min_m:
        return height_m / min_m if min_m > 0 else 0.0
    if height_m <= max_m:
        return 1.0
    ideal_range = max(max_m - min_m, max_m)  # fallback prevents zero-div
    overshoot = height_m - max_m
    return max(0.0, 1.0 - overshoot / ideal_range)


def _period_score(period_s: float, min_s: float) -> float:
    """Score a period in seconds relative to min_s.

    Below min_s, return period_s / min_s. At min_s, the score drops to 0.75,
    then rises to a cap of 1.0. A zero min_s raises ZeroDivisionError.
    """
    if period_s < min_s:
        return period_s / min_s
    # Gently increasing benefit beyond minimum, capped
    return min(1.0, 0.75 + (period_s - min_s) / (min_s * 2))


def _wind_score(speed_mps: float, direction_deg: Optional[float], profile: SpotProfile) -> float:
    """Score wind speed in meters per second and optional direction in degrees.

    Use the speed score alone when either the observed or ideal direction
    is missing; otherwise combine 70% speed and 30% direction. A zero profile
    maximum wind speed raises ZeroDivisionError.
    """
    speed_factor = max(0.0, 1.0 - speed_mps / profile.max_wind_speed_mps)
    if profile.ideal_wind_direction_deg is None or direction_deg is None:
        return speed_factor
    dir_factor = _direction_score(
        direction_deg,
        profile.ideal_wind_direction_deg,
        profile.ideal_wind_direction_tolerance_deg,
    )
    return speed_factor * 0.7 + dir_factor * 0.3


def score_hour(h: HourlyConditions, profile: SpotProfile) -> tuple[float, float, dict]:
    """Return the weighted score, confidence, and unweighted component scores.

    Prefer combined height and period, falling back to swell; prefer swell
    direction, falling back to combined direction. Exclude missing components
    from the weighted average. An unspecified ideal swell direction supplies
    0.7 without increasing confidence, which counts observed components out
    of four. With no contributing components, score and confidence are zero.

    Scale the score by ten and round it and confidence to two decimal places;
    inputs are not clamped. Invalid profile scales can raise ZeroDivisionError.
    """
    components: dict[str, Optional[float]] = {
        "wave_height": None,
        "wave_period": None,
        "wind": None,
        "direction": None,
    }
    data_count = 0
    total_fields = 4

    # Wave height — prefer combined, fall back to swell; 0.0 is valid
    height = h.wave_height_m if h.wave_height_m is not None else h.swell_height_m
    if height is not None:
        components["wave_height"] = _height_score(
            height, profile.ideal_wave_height_min_m, profile.ideal_wave_height_max_m
        )
        data_count += 1

    # Wave period — prefer combined, fall back to swell; 0.0 is valid
    period = h.wave_period_s if h.wave_period_s is not None else h.swell_period_s
    if period is not None:
        components["wave_period"] = _period_score(period, profile.ideal_period_min_s)
        data_count += 1

    # Wind
    if h.wind_speed_mps is not None:
        components["wind"] = _wind_score(
            h.wind_speed_mps, h.wind_direction_deg, profile
        )
        data_count += 1

    # Swell direction — prefer swell, fall back to combined; 0.0° is valid
    swell_dir = h.swell_direction_deg if h.swell_direction_deg is not None else h.wave_direction_deg
    if swell_dir is not None and profile.ideal_swell_direction_deg is not None:
        components["direction"] = _direction_score(
            swell_dir,
            profile.ideal_swell_direction_deg,
            profile.ideal_swell_direction_tolerance_deg,
        )
        data_count += 1
    elif profile.ideal_swell_direction_deg is None:
        components["direction"] = 0.7   # neutral when no ideal defined

    # Build weighted score (use neutral 0.5 for missing components)
    weights = {
        "wave_height": _W_HEIGHT,
        "wave_period": _W_PERIOD,
        "wind": _W_WIND,
        "direction": _W_DIR,
    }
    total_weight = 0.0
    raw = 0.0
    for key, w in weights.items():
        v = components[key]
        if v is not None:
            raw += v * w
            total_weight += w

    if total_weight == 0:
        return 0.0, 0.0, components  # type: ignore[return-value]

    score_0_1 = raw / total_weight
    score = round(score_0_1 * 10, 2)
    confidence = round(data_count / total_fields, 2)

    return score, confidence, components


def score_all(hourly: list[HourlyConditions], profile: SpotProfile) -> list[HourlyConditions]:
    """Return copies with scores, confidence, and component scores filled in.

    Preserve input order and leave original conditions unchanged. Scoring
    errors, including ZeroDivisionError from invalid profile scales, propagate.
    """
    scored: list[HourlyConditions] = []
    for h in hourly:
        s, c, comp = score_hour(h, profile)
        scored.append(
            h.model_copy(
                update={
                    "score": s,
                    "confidence": c,
                    "score_wave_height": comp.get("wave_height"),
                    "score_wave_period": comp.get("wave_period"),
                    "score_wind": comp.get("wind"),
                    "score_direction": comp.get("direction"),
                }
            )
        )
    return scored


def best_window(hourly: list[HourlyConditions], min_score: float = 5.0) -> Optional[BestWindow]:
    """Choose the highest rounded mean score among qualifying runs and their suffixes.

    Expect chronological input. Keep entries with score >= min_score and
    extend each candidate until the next eligible timestamp is over 90 minutes
    away. Require at least three entries; return None if none qualify. Ties
    keep the first candidate. Start and end are the first and last sample
    timestamps, and mean and peak scores are rounded to two decimal places.
    """
    eligible = [h for h in hourly if h.score is not None and h.score >= min_score]
    if not eligible:
        return None

    best: Optional[BestWindow] = None
    for i, start in enumerate(eligible):
        window = [start]
        for nxt in eligible[i + 1:]:
            if (nxt.timestamp - window[-1].timestamp).total_seconds() > 3600 * 1.5:
                break
            window.append(nxt)
        if len(window) < 3:
            continue
        mean_s = sum(h.score for h in window) / len(window)  # type: ignore[union-attr]
        peak_s = max(h.score for h in window)  # type: ignore[union-attr]
        candidate = BestWindow(
            start=window[0].timestamp,
            end=window[-1].timestamp,
            mean_score=round(mean_s, 2),
            peak_score=round(peak_s, 2),
        )
        if best is None or candidate.mean_score > best.mean_score:
            best = candidate

    return best
