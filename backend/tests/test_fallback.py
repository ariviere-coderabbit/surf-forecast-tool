"""Deterministic outage, expiry, and recovery scenarios; no provider network calls."""
import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.adapters import noaa_gfswave as noaa
from app.merger import build_hourly
from app.models import WaveMeasurement
from app.scorer import score_all
from app.spot_profiles import get_profile

NOW = datetime(2026, 11, 4, 18, tzinfo=timezone.utc)


def snapshot(path, cycle, *, valid_time=NOW.isoformat(), height=1.5):
    file = path / f"gfswave_{cycle}.json"
    file.write_text(json.dumps([{
        "valid_time": valid_time,
        "fields": {"HTSGW": {"lats": [9.6], "lons": [-84.6], "vals": [height]}},
    }]))
    return file


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(noaa.settings, "noaa_data_dir", tmp_path)
    monkeypatch.setattr(noaa.settings, "noaa_max_cycle_age_hours", 24)
    return tmp_path


def test_older_cycle_then_fresh_recovery(cache):
    snapshot(cache, "20261104_06")
    old = noaa.load_measurements(9.6, -84.6, now=NOW)
    assert old[0].is_fallback
    assert old[0].forecast_cycle.hour == 6
    snapshot(cache, "20261104_12", height=2.0)
    fresh = noaa.load_measurements(9.6, -84.6, now=NOW)
    assert not fresh[0].is_fallback
    assert fresh[0].wave_height_m == 2.0


@pytest.mark.parametrize("bad", ["{", "{}", "[]", '[{"valid_time":"bad"}]'])
def test_corrupt_latest_uses_previous(cache, bad):
    snapshot(cache, "20261104_06")
    (cache / "gfswave_20261104_12.json").write_text(bad)
    assert noaa.load_measurements(9.6, -84.6, now=NOW)[0].is_fallback


def test_age_is_issue_time_not_file_mtime_or_valid_time(cache):
    snapshot(cache, "20261103_12", valid_time="2026-11-05T18:00:00+00:00")
    assert noaa.load_measurements(9.6, -84.6, now=NOW) == []
    snapshot(cache, "20261103_18")  # Exactly 24 hours is allowed.
    assert noaa.load_measurements(9.6, -84.6, now=NOW)


@pytest.mark.parametrize("valid_time,height", [
    ("2026-11-04T15:00:00+00:00", 1.5),
    ("2026-11-04T18:00:00", 1.5),
    (NOW.isoformat(), None),
])
def test_unusable_latest_uses_previous(cache, valid_time, height):
    snapshot(cache, "20261104_06")
    snapshot(cache, "20261104_12", valid_time=valid_time, height=height)
    assert noaa.load_measurements(9.6, -84.6, now=NOW)[0].forecast_cycle.hour == 6


def test_future_cycle_is_not_selected(cache):
    snapshot(cache, "20261104_18")
    assert noaa.load_measurements(9.6, -84.6, now=NOW) == []


def test_fallback_changes_confidence_not_surf_score():
    fresh = WaveMeasurement(timestamp=NOW, provider="noaa", model="gfs", wave_height_m=1.5)
    profile = get_profile(9.6, -84.6)
    normal = score_all(build_hourly([[fresh]], [], {}), profile)[0]
    old = score_all(build_hourly([[fresh.model_copy(update={"is_fallback": True})]], [], {}), profile)[0]
    assert old.uses_fallback
    assert old.score == normal.score
    assert old.confidence == round(normal.confidence * 0.75, 2)


@pytest.mark.anyio
async def test_api_fallback_not_cached_and_recovers(client, cache, monkeypatch):
    monkeypatch.setattr("app.cache.forecast_cache._dir", cache / "responses")
    (cache / "responses").mkdir()
    old = WaveMeasurement(timestamp=NOW, provider="noaa-ncep", model="GFS-Wave-0.16",
                          wave_height_m=1.5, is_fallback=True, forecast_cycle=NOW)
    with (
        patch("app.main.open_meteo_waves.fetch_waves", return_value=[]),
        patch("app.main.open_meteo_wind.fetch_wind", return_value=[]),
        patch("app.main.open_meteo_sealevel.fetch_sea_level", return_value=[]),
        patch.object(noaa, "maybe_refresh", new_callable=AsyncMock),
        patch.object(noaa, "load_measurements", side_effect=[[old], [old.model_copy(update={"is_fallback": False})], []]),
    ):
        first = await client.get("/api/forecast?lat=9.6&lon=-84.6")
        assert first.status_code == 200
        body = first.json()
        assert body["providers"][1]["is_fallback"]
        assert body["providers"][1]["status"] == "partial"
        assert body["hourly"][0]["uses_fallback"]
        assert body["warnings"]
        second = await client.get("/api/forecast?lat=9.6&lon=-84.6")
        assert not second.json()["providers"][1]["is_fallback"]
        empty = await client.get("/api/forecast?lat=9.7&lon=-84.6")
        assert empty.status_code == 503


@pytest.mark.anyio
async def test_rollover_refresh_not_blocked_by_previous_success(cache, monkeypatch):
    import asyncio
    import time
    monkeypatch.setattr(noaa, "_running_task", None)
    monkeypatch.setattr(noaa, "_last_refresh", time.monotonic())
    with patch.object(noaa, "_refresh_cycle", new_callable=AsyncMock) as refresh:
        await noaa.maybe_refresh()
        await noaa._running_task
        refresh.assert_awaited_once()


@pytest.mark.anyio
async def test_refresh_publishes_snapshot_and_keeps_old_on_total_failure(cache, monkeypatch):
    monkeypatch.setattr(noaa, "_FHOURS", [0])
    monkeypatch.setattr(noaa.settings, "noaa_request_pace", 0)
    monkeypatch.setattr(noaa, "_last_refresh", None)
    monkeypatch.setattr(noaa, "_running_task", None)
    payload = {"valid_time": NOW.isoformat(), "fields": {}}
    with patch.object(noaa, "_fetch_one_hour", new_callable=AsyncMock, return_value=payload):
        await noaa._refresh_cycle("20261104", "12")
    target = cache / "gfswave_20261104_12.json"
    assert json.loads(target.read_text()) == [payload]
    assert not list(cache.glob("*.tmp"))
    with patch.object(noaa, "_fetch_one_hour", new_callable=AsyncMock, return_value=None):
        await noaa._refresh_cycle("20261104", "12")
    assert json.loads(target.read_text()) == [payload]
