from __future__ import annotations

import os
from pathlib import Path

from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Directories
    cache_dir: Path = Path(__file__).parent.parent / ".cache"
    noaa_data_dir: Path = Path(__file__).parent.parent / "data" / "noaa"

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
    open_meteo_wave_model: str = "icon_wave"

    # HTTP timeouts (seconds)
    http_timeout: float = 30.0


settings = Settings()
settings.cache_dir.mkdir(parents=True, exist_ok=True)
settings.noaa_data_dir.mkdir(parents=True, exist_ok=True)
