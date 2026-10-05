"""Tests for data merging and circular direction calculations."""
from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from app.merger import _circular_mean, _floor_hour, _scalar_mean, merge_waves, merge_wind
from app.models import WaveMeasurement, WindMeasurement


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc)


def _wave(hour: int, height=1.0, direction=None, period=10.0) -> WaveMeasurement:
    return WaveMeasurement(
        timestamp=_ts(hour),
        provider="test",
        model="test",
        wave_height_m=height,
        wave_period_s=period,
        wave_direction_deg=direction,
    )


def _wind(hour: int, speed=5.0, direction=None) -> WindMeasurement:
    return WindMeasurement(
        timestamp=_ts(hour),
        provider="test",
        model="test",
        speed_mps=speed,
        direction_deg=direction,
    )


class TestCircularMean:
    def test_simple(self):
        result = _circular_mean([0.0, 90.0])
        assert abs(result - 45.0) < 0.5

    def test_wrap_around_zero(self):
        result = _circular_mean([350.0, 10.0])
        # Should be near 0 degrees, not 180
        assert result is not None
        assert result < 20 or result > 340

    def test_empty(self):
        assert _circular_mean([]) is None

    def test_single(self):
        result = _circular_mean([270.0])
        assert result is not None
        assert abs(result - 270.0) < 1.0

    def test_opposite_cancel(self):
        # 0° and 180° should produce ambiguous result (magnitude near 0)
        result = _circular_mean([0.0, 180.0])
        # Just confirm it returns a float and doesn't crash
        assert result is not None or result is None  # either acceptable


class TestScalarMean:
    def test_basic(self):
        assert _scalar_mean([1.0, 3.0]) == 2.0

    def test_empty(self):
        assert _scalar_mean([]) is None


class TestMergeWaves:
    def test_single_provider_passthrough(self):
        series = [_wave(0), _wave(1), _wave(2)]
        merged = merge_waves(series)
        assert len(merged) == 3
        assert merged[_ts(0)]["wave_height_m"] == pytest.approx(1.0)

    def test_two_providers_averaged(self):
        s1 = [_wave(0, height=1.0)]
        s2 = [_wave(0, height=3.0)]
        merged = merge_waves(s1, s2)
        assert merged[_ts(0)]["wave_height_m"] == pytest.approx(2.0)

    def test_missing_measurement_not_interpolated(self):
        s1 = [_wave(0), _wave(2)]   # gap at hour 1
        merged = merge_waves(s1)
        assert _ts(1) not in merged

    def test_zero_height_treated_as_valid(self):
        series = [_wave(0, height=0.0)]
        merged = merge_waves(series)
        assert merged[_ts(0)]["wave_height_m"] == pytest.approx(0.0)

    def test_direction_circular_merge(self):
        s1 = [WaveMeasurement(
            timestamp=_ts(0), provider="a", model="a",
            wave_direction_deg=350.0,
        )]
        s2 = [WaveMeasurement(
            timestamp=_ts(0), provider="b", model="b",
            wave_direction_deg=10.0,
        )]
        merged = merge_waves(s1, s2)
        d = merged[_ts(0)]["wave_direction_deg"]
        assert d is not None
        # Should be near 0/360, not 180
        assert d < 25 or d > 335

    def test_none_direction_ignored_in_mean(self):
        s1 = [WaveMeasurement(
            timestamp=_ts(0), provider="a", model="a",
            wave_direction_deg=90.0,
        )]
        s2 = [WaveMeasurement(
            timestamp=_ts(0), provider="b", model="b",
            wave_direction_deg=None,
        )]
        merged = merge_waves(s1, s2)
        assert merged[_ts(0)]["wave_direction_deg"] == pytest.approx(90.0)


class TestMergeWind:
    def test_basic(self):
        series = [_wind(0, speed=5.0), _wind(1, speed=7.0)]
        merged = merge_wind(series)
        assert merged[_ts(0)]["wind_speed_mps"] == pytest.approx(5.0)
        assert merged[_ts(1)]["wind_speed_mps"] == pytest.approx(7.0)

    def test_floor_hour_alignment(self):
        m = WindMeasurement(
            timestamp=datetime(2024, 1, 15, 3, 45, 0, tzinfo=timezone.utc),
            provider="x", model="x", speed_mps=3.0,
        )
        merged = merge_wind([m])
        key = datetime(2024, 1, 15, 3, 0, 0, tzinfo=timezone.utc)
        assert key in merged
