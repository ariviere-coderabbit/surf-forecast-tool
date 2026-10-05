from __future__ import annotations

import os
from pathlib import Path

from pydantic import ConfigDict, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Directories
    cache_dir: Path = Path(__file__).parent.parent / ".cache"
    noaa_data_dir: Path = Path(__file__).parent.parent / "data" / "noaa"

    # Durable personal journal, never place this inside the forecast cache.
    journal_db_path: Path = Path(__file__).parent.parent / "data" / "journal.sqlite3"
    match_height_m: float = Field(0.5, gt=0, allow_inf_nan=False)
    match_period_s: float = Field(2.0, gt=0, allow_inf_nan=False)
    match_wind_mps: float = Field(2.0, gt=0, allow_inf_nan=False)
    match_direction_deg: float = Field(45.0, gt=0, allow_inf_nan=False)
    match_sea_level_m: float = Field(0.3, gt=0, allow_inf_nan=False)

    # Cache TTLs (seconds)
    geocode_cache_ttl: int = 86_400   # 24 h
    forecast_cache_ttl: int = 3_600   # 1 h
    noaa_refresh_interval: int = 21_600  # 6 h
    noaa_request_pace: float = 10.0   # seconds between NOAA requests

    # NOAA region for GFS-Wave subsetting (Central America default)
    noaa_region_left_lon: float = -95.0
    noaa_region_right_lon: float = -65.0
    noaa_region_top_lat: float = 25.0
    noaa_region_bottom_lat: float = 5.0

    # Open-Meteo wave model (non-GFS)
    open_meteo_wave_model: str = "gwam"

    # HTTP timeouts (seconds)
    http_timeout: float = 30.0


settings = Settings()
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.noaa_data_dir.mkdir(parents=True, exist_ok=True)
