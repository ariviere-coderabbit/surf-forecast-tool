"""Open-Meteo geocoding with 24-hour disk cache and accent-insensitive matching."""
from __future__ import annotations

import unicodedata
from typing import Optional

import httpx

from app.cache import geocode_cache
from app.config import settings
from app.models import GeoCandidate, GeocodeResponse

_GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"


def _strip_accents(s: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )


def _normalise(s: str) -> str:
    return _strip_accents(s).lower().strip()


def _parse_candidates(raw: list[dict]) -> list[GeoCandidate]:
    out: list[GeoCandidate] = []
    for item in raw:
        try:
            out.append(
                GeoCandidate(
                    id=item["id"],
                    name=item["name"],
                    country=item.get("country", ""),
                    country_code=item.get("country_code", ""),
                    admin1=item.get("admin1"),
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                    timezone=item.get("timezone", "UTC"),
                    population=item.get("population"),
                )
            )
        except (KeyError, TypeError):
            continue
    return out


def _filter_by_country(candidates: list[GeoCandidate], country_hint: str) -> list[GeoCandidate]:
    """Narrow candidates whose country name or code matches accent-insensitively."""
    norm = _normalise(country_hint)
    matched = [
        c for c in candidates
        if _normalise(c.country) == norm or _normalise(c.country_code) == norm
    ]
    return matched if matched else candidates


async def geocode(query: str, country_hint: Optional[str] = None) -> GeocodeResponse:
    cache_key = f"{query}|{country_hint or ''}"
    cached = geocode_cache.get(cache_key)
    if cached is not None:
        candidates = [GeoCandidate(**c) for c in cached["candidates"]]
        selected = GeoCandidate(**cached["selected"]) if cached.get("selected") else None
        return GeocodeResponse(query=query, candidates=candidates, selected=selected)

    async with httpx.AsyncClient(timeout=settings.http_timeout) as client:
        resp = await client.get(
            _GEO_URL,
            params={"name": query, "count": 10, "language": "en", "format": "json"},
        )
        resp.raise_for_status()

    raw_results = resp.json().get("results", [])
    candidates = _parse_candidates(raw_results)

    if country_hint:
        candidates = _filter_by_country(candidates, country_hint)

    selected = candidates[0] if len(candidates) == 1 else None

    geocode_cache.set(
        cache_key,
        {
            "candidates": [c.model_dump(mode="json") for c in candidates],
            "selected": selected.model_dump(mode="json") if selected else None,
        },
    )
    return GeocodeResponse(query=query, candidates=candidates, selected=selected)
