"""Tests for geocoding with mocked HTTP."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.geocoding import _normalise, _strip_accents, geocode
from app.models import GeoCandidate


_JACO_RESULT = {
    "results": [
        {
            "id": 1,
            "name": "Jacó",
            "country": "Costa Rica",
            "country_code": "CR",
            "admin1": "Puntarenas",
            "latitude": 9.613,
            "longitude": -84.628,
            "timezone": "America/Costa_Rica",
            "population": 5000,
        }
    ]
}

_MULTI_RESULT = {
    "results": [
        {
            "id": 1,
            "name": "Springfield",
            "country": "United States",
            "country_code": "US",
            "latitude": 37.2,
            "longitude": -93.3,
            "timezone": "America/Chicago",
        },
        {
            "id": 2,
            "name": "Springfield",
            "country": "United Kingdom",
            "country_code": "GB",
            "latitude": 52.5,
            "longitude": -1.5,
            "timezone": "Europe/London",
        },
    ]
}


@pytest.mark.anyio
async def test_geocode_single_result(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.geocode_cache._dir", tmp_path)

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: _JACO_RESULT

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        result = await geocode("Jaco, Costa Rica")

    assert len(result.candidates) == 1
    assert result.candidates[0].name == "Jacó"
    assert result.selected is not None
    assert result.selected.country_code == "CR"


@pytest.mark.anyio
async def test_geocode_ambiguous_no_country(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.geocode_cache._dir", tmp_path)

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: _MULTI_RESULT

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        result = await geocode("Springfield")

    assert len(result.candidates) == 2
    assert result.selected is None


@pytest.mark.anyio
async def test_geocode_country_hint_narrows(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.geocode_cache._dir", tmp_path)

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: _MULTI_RESULT

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        result = await geocode("Springfield", country_hint="United States")

    assert len(result.candidates) == 1
    assert result.candidates[0].country_code == "US"


@pytest.mark.anyio
async def test_geocode_accent_insensitive_country(tmp_path, monkeypatch):
    monkeypatch.setattr("app.cache.geocode_cache._dir", tmp_path)

    mock_resp = AsyncMock()
    mock_resp.raise_for_status = lambda: None
    mock_resp.json = lambda: {
        "results": [
            {
                "id": 10,
                "name": "Bogotá",
                "country": "Colombia",
                "country_code": "CO",
                "latitude": 4.7,
                "longitude": -74.1,
                "timezone": "America/Bogota",
            }
        ]
    }

    with patch("httpx.AsyncClient.get", return_value=mock_resp):
        result = await geocode("Bogota", country_hint="Colombia")

    assert len(result.candidates) == 1


def test_strip_accents():
    assert _strip_accents("Jacó") == "Jaco"
    assert _strip_accents("México") == "Mexico"
    assert _strip_accents("España") == "Espana"


def test_normalise_lowercases():
    assert _normalise("Costa Rica") == "costa rica"
    assert _normalise("COSTA RICA") == "costa rica"
