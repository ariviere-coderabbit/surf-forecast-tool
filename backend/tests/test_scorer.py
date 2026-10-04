"""Tests for surfability scoring."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import HourlyConditions, SpotProfile
from app.scorer import best_window, score_all, score_hour, _direction_score, _height_score


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc)


def _profile(**kwargs) -> SpotProfile:
    defaults = dict(
        name="Test",
        latitude=0.0,
        longitude=0.0,
        ideal_swell_direction_deg=200.0,
        ideal_swell_direction_tolerance_deg=50.0,
        ideal_wave_height_min_m=0.5,
        ideal_wave_height_max_m=2.0,
        ideal_period_min_s=8.0,
        ideal_wind_direction_deg=60.0,
        ideal_wind_direction_tolerance_deg=45.0,
        max_wind_speed_mps=8.0,
    )
    defaults.update(kwargs)
    return SpotProfile(**defaults)


def _hour(**kwargs) -> HourlyConditions:
    defaults = dict(timestamp=_ts(0))
    defaults.update(kwargs)
    return HourlyConditions(**defaults)


class TestDirectionScore:
    def test_on_ideal(self):
        assert _direction_score(200.0, 200.0, 50.0) == pytest.approx(1.0)

    def test_at_tolerance_boundary(self):
        assert _direction_score(250.0, 200.0, 50.0) == pytest.approx(0.0)

    def test_partial_match(self):
        s = _direction_score(225.0, 200.0, 50.0)
        assert 0.0 < s < 1.0

    def test_wrap_around_360(self):
        # 350° ideal, swell at 5° = 15° difference
        s = _direction_score(5.0, 350.0, 50.0)
        assert s > 0.5

    def test_opposite_direction(self):
        assert _direction_score(20.0, 200.0, 50.0) == pytest.approx(0.0)


class TestHeightScore:
    def test_zero_swell(self):
        assert _height_score(0.0, 0.5, 2.0) == pytest.approx(0.0)

    def test_below_min(self):
        s = _height_score(0.25, 0.5, 2.0)
        assert s == pytest.approx(0.5)

    def test_ideal_midpoint(self):
        # Mid between 0.5 and 2.0 is 1.25
        s = _height_score(1.25, 0.5, 2.0)
        assert s == pytest.approx(1.0)

    def test_too_big(self):
        s = _height_score(5.0, 0.5, 2.0)
        assert s < 0.5

    def test_at_max(self):
        # At max is still acceptable (score should be >= 0)
        s = _height_score(2.0, 0.5, 2.0)
        assert s >= 0.0


class TestScoreHour:
    def test_no_data_returns_zero_confidence(self):
        h = _hour()
        profile = _profile()
        score, conf, _ = score_hour(h, profile)
        assert conf == pytest.approx(0.0)

    def test_ideal_conditions_high_score(self):
        h = _hour(
            wave_height_m=1.2,
            wave_period_s=12.0,
            wave_direction_deg=200.0,
            swell_height_m=1.2,
            swell_direction_deg=200.0,
            wind_speed_mps=2.0,
            wind_direction_deg=60.0,
        )
        profile = _profile()
        score, conf, _ = score_hour(h, profile)
        assert score >= 7.0
        assert conf >= 0.75

    def test_zero_swell_low_score(self):
        h = _hour(
            wave_height_m=0.0,
            wave_period_s=5.0,
            wind_speed_mps=15.0,
        )
        profile = _profile()
        score, _, _ = score_hour(h, profile)
        assert score < 4.0

    def test_period_mismatch_reduces_score(self):
        h = _hour(wave_height_m=1.0, wave_period_s=4.0)
        profile = _profile(ideal_period_min_s=10.0)
        score, _, comp = score_hour(h, profile)
        assert comp["wave_period"] is not None
        assert comp["wave_period"] < 0.5


class TestScoreAll:
    def test_scores_applied_to_all_hours(self):
        hours = [_hour(timestamp=_ts(i), wave_height_m=1.0) for i in range(5)]
        profile = _profile()
        scored = score_all(hours, profile)
        assert len(scored) == 5
        assert all(h.score is not None for h in scored)


class TestBestWindow:
    def test_no_eligible_hours(self):
        hours = [_hour(timestamp=_ts(i), score=2.0) for i in range(6)]
        assert best_window(hours, min_score=5.0) is None

    def test_finds_window(self):
        hours = [
            _hour(timestamp=_ts(i), score=7.0 if 2 <= i <= 6 else 2.0)
            for i in range(10)
        ]
        bw = best_window(hours, min_score=5.0)
        assert bw is not None
        assert bw.mean_score >= 5.0

    def test_window_requires_minimum_three_hours(self):
        hours = [
            _hour(timestamp=_ts(0), score=8.0),
            _hour(timestamp=_ts(1), score=8.0),
            _hour(timestamp=_ts(5), score=8.0),  # gap breaks continuity
        ]
        bw = best_window(hours, min_score=5.0)
        # Only 2 consecutive, then gap — should be None
        assert bw is None
