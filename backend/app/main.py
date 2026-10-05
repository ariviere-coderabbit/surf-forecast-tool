"""FastAPI application — surf forecast tool backend."""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from datetime import timezone as tz
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.adapters import noaa_gfswave
from app.geocoding import geocode
from app.models import (
    ForecastResponse,
    GeocodeResponse,
)
from app.forecast import get_forecast
from app.sessions import router as sessions_router

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(noaa_gfswave.maybe_refresh())
    yield


app = FastAPI(title="Surf Forecast Tool", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)


app.include_router(sessions_router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": datetime.now(tz.utc).isoformat()}


@app.get("/api/geocode", response_model=GeocodeResponse)
async def geocode_endpoint(
    q: str = Query(..., description="Location search string"),
    country: Optional[str] = Query(None, description="Optional country hint"),
):
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query must not be empty")
    try:
        result = await geocode(q.strip(), country)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Geocoding service error: {exc}")
    if not result.candidates:
        raise HTTPException(status_code=404, detail="No locations found")
    return result


@app.get("/api/forecast", response_model=ForecastResponse)
async def forecast_endpoint(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    timezone: str = Query("UTC"),
    name: str = Query(""),
    country: str = Query(""),
    country_code: str = Query(""),
):
    return await get_forecast(lat, lon, timezone, name, country, country_code)
