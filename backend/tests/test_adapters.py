"""Tests for data adapters with mocked HTTP responses."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest

from app.adapters.open_meteo_waves import fetch_waves, _haversine_km
from app.adapters.open_meteo_wind import fetch_wind
from app.adapters.noaa_gfswave import _latest_cycle, load_measurements, _nearest_point


# ---------------------------------------------------------------------------
# Open-Meteo waves
# ---------------------------------------------------------------------------

_OM_WAVE_RESPONSE = {
    "latitude": 9.625,
    "longitude": -84.625,
    "hourly": {
        "time": ["2024-01-15T00:00", "2024-01-15T01:00"],
        "wave_height": [1.2, 1.3],
        "wave_direction": [200.0, 205.0],
        "wave_period": [12.0, 11.5],
        "wind_wave_height": [0.4, 0.45],
        "wind_wave_direction": [180.0, 185.0],
        "wind_wave_period": [6.0, 5.5],
        "swell_wave_height": [1.0, 1.1],
        "swell_wave_direction": [210.0, 208.0],
        "swell_wave_period": [14.0, 13.5],
    },
}


@pytest.mark.anyio
async def test_fetch_waves_parsing():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: _OM_WAVE_RESPONSE

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        measurements = await fetch_waves(9.613, -84.628)

    assert len(measurements) == 2
    m = measurements[0]
    assert m.wave_height_m == pytest.approx(1.2)
    assert m.wave_direction_deg == pytest.approx(200.0)
    assert m.swell_height_m == pytest.approx(1.0)
    assert m.provider == "open-meteo"
    assert m.model == "icon_wave"
    assert m.timestamp.tzinfo is not None  # UTC-aware


@pytest.mark.anyio
async def test_fetch_waves_sampling_distance():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: _OM_WAVE_RESPONSE

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        measurements = await fetch_waves(9.613, -84.628)

    assert measurements[0].sampling_distance_km is not None
    assert measurements[0].sampling_distance_km < 5.0  # grid point very close


@pytest.mark.anyio
async def test_fetch_waves_null_values():
    response = {
        "latitude": 9.625,
        "longitude": -84.625,
        "hourly": {
            "time": ["2024-01-15T00:00"],
            "wave_height": [None],
            "wave_direction": [None],
            "wave_period": [None],
            "wind_wave_height": [None],
            "wind_wave_direction": [None],
            "wind_wave_period": [None],
            "swell_wave_height": [None],
            "swell_wave_direction": [None],
            "swell_wave_period": [None],
        },
    }
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: response

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        measurements = await fetch_waves(9.613, -84.628)

    assert measurements[0].wave_height_m is None
    assert measurements[0].swell_direction_deg is None


# ---------------------------------------------------------------------------
# Open-Meteo wind
# ---------------------------------------------------------------------------

_OM_WIND_RESPONSE = {
    "latitude": 9.625,
    "longitude": -84.625,
    "hourly": {
        "time": ["2024-01-15T00:00", "2024-01-15T01:00"],
        "wind_speed_10m": [3.5, 4.0],
        "wind_direction_10m": [70.0, 75.0],
        "wind_gusts_10m": [6.0, 7.0],
    },
}


@pytest.mark.anyio
async def test_fetch_wind_parsing():
    mock_resp = MagicMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: _OM_WIND_RESPONSE

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        measurements = await fetch_wind(9.613, -84.628)

    assert len(measurements) == 2
    m = measurements[0]
    assert m.speed_mps == pytest.approx(3.5)
    assert m.direction_deg == pytest.approx(70.0)
    assert m.gust_mps == pytest.approx(6.0)
    assert m.provider == "open-meteo"


# ---------------------------------------------------------------------------
# NOAA adapter
# ---------------------------------------------------------------------------

def test_latest_cycle_returns_valid_hh():
    now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    date_str, hh = _latest_cycle(now)
    assert hh in ("00", "06", "12", "18")
    # With 5h lag, at 10:00 UTC we can expect the 00 cycle
    assert hh == "00"


def test_latest_cycle_evening():
    now = datetime(2024, 1, 15, 20, 0, 0, tzinfo=timezone.utc)
    date_str, hh = _latest_cycle(now)
    assert hh == "12"


def test_nearest_point_basic():
    lats = [9.0, 9.5, 10.0]
    lons = [-85.0, -84.5, -84.0]
    vals = [1.0, 2.0, 3.0]
    val, glat, glon = _nearest_point(lats, lons, vals, 9.6, -84.6)
    assert val == pytest.approx(2.0)
    assert glat == pytest.approx(9.5)


def test_nearest_point_skips_missing():
    lats = [9.5]
    lons = [-84.5]
    vals = [None]
    val, glat, glon = _nearest_point(lats, lons, vals, 9.5, -84.5)
    assert val is None


def test_load_measurements_empty_when_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("app.adapters.noaa_gfswave.settings.noaa_data_dir", tmp_path)
    result = load_measurements(9.613, -84.628)
    assert result == []


def test_load_measurements_from_synthetic_cache(tmp_path, monkeypatch):
    monkeypatch.setattr("app.adapters.noaa_gfswave.settings.noaa_data_dir", tmp_path)

    # Build a minimal synthetic NOAA cache entry
    lats = [9.5, 9.5, 10.0]
    lons = [-84.5, -85.0, -84.5]
    hour_data = [
        {
            "valid_time": "2024-01-15T06:00:00+00:00",
            "fields": {
                "HTSGW": {"lats": lats, "lons": lons, "vals": [1.5, 1.2, 1.0]},
                "PERPW": {"lats": lats, "lons": lons, "vals": [11.0, 10.0, 9.0]},
                "DIRPW": {"lats": lats, "lons": lons, "vals": [200.0, 205.0, 195.0]},
                "SWELL": {"lats": lats, "lons": lons, "vals": [1.3, 1.0, 0.9]},
                "SWPER": {"lats": lats, "lons": lons, "vals": [13.0, 12.0, 11.0]},
                "SWDIR": {"lats": lats, "lons": lons, "vals": [210.0, 208.0, 205.0]},
            },
        }
    ]

    now = datetime(2024, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
    with patch("app.adapters.noaa_gfswave.datetime") as mock_dt:
        mock_dt.now.return_value = now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

        date_str, hh = "20240115", "00"
        path = tmp_path / f"gfswave_{date_str}_{hh}.json"
        path.write_text(json.dumps(hour_data))

        with patch("app.adapters.noaa_gfswave._latest_cycle", return_value=(date_str, hh)):
            result = load_measurements(9.613, -84.628)

    assert len(result) == 1
    m = result[0]
    assert m.wave_height_m == pytest.approx(1.5)  # nearest point is lats[0]
    assert m.provider == "noaa-ncep"
    assert m.model == "GFS-Wave-0.16"
    assert m.sampling_distance_km is not None


# ---------------------------------------------------------------------------
# Haversine
# ---------------------------------------------------------------------------

def test_haversine_same_point():
    assert _haversine_km(9.6, -84.6, 9.6, -84.6) == pytest.approx(0.0)


def test_haversine_known_distance():
    # ~111 km per degree latitude
    d = _haversine_km(0.0, 0.0, 1.0, 0.0)
    assert abs(d - 111.2) < 1.0
