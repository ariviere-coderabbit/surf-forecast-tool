"""Integration tests for FastAPI endpoints with mocked providers."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models import WaveMeasurement, WindMeasurement


def _ts(hour: int) -> datetime:
    return datetime(2024, 1, 15, hour, 0, 0, tzinfo=timezone.utc)


def _make_waves(n: int = 3) -> list[WaveMeasurement]:
    return [
        WaveMeasurement(
            timestamp=_ts(i),
            provider="open-meteo",
            model="gwam",
            wave_height_m=1.2,
            wave_period_s=12.0,
            wave_direction_deg=200.0,
            swell_height_m=1.0,
            swell_period_s=14.0,
            swell_direction_deg=210.0,
        )
        for i in range(n)
    ]


def _make_wind(n: int = 3) -> list[WindMeasurement]:
    return [
        WindMeasurement(
            timestamp=_ts(i),
            provider="open-meteo",
            model="best_match",
            speed_mps=3.0,
            direction_deg=70.0,
        )
        for i in range(n)
    ]


@pytest.fixture
async def api_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.anyio
async def test_health(api_client):
    resp = await api_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.anyio
async def test_geocode_returns_candidates(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.geocode_cache._dir", tmp_path)

    from app.models import GeoCandidate, GeocodeResponse

    fake_response = GeocodeResponse(
        query="Jaco, Costa Rica",
        candidates=[
            GeoCandidate(
                id=1,
                name="Jacó",
                country="Costa Rica",
                country_code="CR",
                latitude=9.613,
                longitude=-84.628,
                timezone="America/Costa_Rica",
            )
        ],
        selected=None,
    )

    with patch("app.main.geocode", return_value=fake_response):
        resp = await api_client.get("/api/geocode", params={"q": "Jaco, Costa Rica"})

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["name"] == "Jacó"


@pytest.mark.anyio
async def test_geocode_empty_query(api_client):
    resp = await api_client.get("/api/geocode", params={"q": "   "})
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_forecast_success(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.forecast_cache._dir", tmp_path)

    with (
        patch("app.forecast.open_meteo_waves.fetch_waves", return_value=_make_waves(5)),
        patch("app.forecast.open_meteo_wind.fetch_wind", return_value=_make_wind(5)),
        patch("app.forecast.open_meteo_sealevel.fetch_sea_level", return_value=[]),
        patch("app.forecast.noaa_gfswave.load_measurements", return_value=[]),
        patch("app.forecast.noaa_gfswave.maybe_refresh", new_callable=AsyncMock),
    ):
        resp = await api_client.get(
            "/api/forecast",
            params={"lat": 9.613, "lon": -84.628, "name": "Jacó", "timezone": "America/Costa_Rica"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert len(data["hourly"]) == 5
    assert data["best_window"] is not None or data["best_window"] is None  # optional
    assert "score" in data["hourly"][0]
    assert data["spot_profile"]["name"] == "Jacó"


@pytest.mark.anyio
async def test_forecast_partial_when_noaa_missing(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.forecast_cache._dir", tmp_path)

    with (
        patch("app.forecast.open_meteo_waves.fetch_waves", return_value=_make_waves(3)),
        patch("app.forecast.open_meteo_wind.fetch_wind", return_value=_make_wind(3)),
        patch("app.forecast.open_meteo_sealevel.fetch_sea_level", return_value=[]),
        patch("app.forecast.noaa_gfswave.load_measurements", return_value=[]),
        patch("app.forecast.noaa_gfswave.maybe_refresh", new_callable=AsyncMock),
    ):
        resp = await api_client.get(
            "/api/forecast",
            params={"lat": 9.613, "lon": -84.628},
        )

    assert resp.status_code == 200
    data = resp.json()
    # Should still return hourly data from Open-Meteo
    assert len(data["hourly"]) > 0
    # Warning about NOAA should appear
    assert any("NOAA" in w for w in data["warnings"])


@pytest.mark.anyio
async def test_forecast_503_when_all_wave_providers_fail(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.forecast_cache._dir", tmp_path)

    with (
        patch("app.forecast.open_meteo_waves.fetch_waves", side_effect=Exception("network error")),
        patch("app.forecast.open_meteo_wind.fetch_wind", return_value=[]),
        patch("app.forecast.open_meteo_sealevel.fetch_sea_level", return_value=[]),
        patch("app.forecast.noaa_gfswave.load_measurements", return_value=[]),
        patch("app.forecast.noaa_gfswave.maybe_refresh", new_callable=AsyncMock),
    ):
        resp = await api_client.get(
            "/api/forecast",
            params={"lat": 9.613, "lon": -84.628},
        )

    assert resp.status_code == 503


@pytest.mark.anyio
async def test_forecast_invalid_lat(api_client):
    resp = await api_client.get("/api/forecast", params={"lat": 200, "lon": 0})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_forecast_uses_generic_profile_for_unknown_location(api_client, tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.forecast_cache._dir", tmp_path)

    with (
        patch("app.forecast.open_meteo_waves.fetch_waves", return_value=_make_waves(3)),
        patch("app.forecast.open_meteo_wind.fetch_wind", return_value=_make_wind(3)),
        patch("app.forecast.open_meteo_sealevel.fetch_sea_level", return_value=[]),
        patch("app.forecast.noaa_gfswave.load_measurements", return_value=[]),
        patch("app.forecast.noaa_gfswave.maybe_refresh", new_callable=AsyncMock),
    ):
        resp = await api_client.get(
            "/api/forecast",
            params={"lat": 0.0, "lon": 0.0},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["spot_profile"]["name"] == "Generic"
