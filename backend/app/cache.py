"""Simple disk-based JSON cache with per-key TTL."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Optional

from app.config import settings


class DiskCache:
    def __init__(self, namespace: str, ttl: int) -> None:
        self._dir = settings.cache_dir / namespace
        self._dir.mkdir(parents=True, exist_ok=True)
        self._ttl = ttl

    def _path(self, key: str) -> Path:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)[:64]
        h = hashlib.sha1(key.encode()).hexdigest()[:8]
        return self._dir / f"{safe}_{h}.json"

    def get(self, key: str) -> Optional[Any]:
        p = self._path(key)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
            if time.time() - data["ts"] > self._ttl:
                p.unlink(missing_ok=True)
                return None
            return data["value"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, value: Any) -> None:
        p = self._path(key)
        try:
            p.write_text(json.dumps({"ts": time.time(), "value": value}))
        except OSError:
            pass

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


geocode_cache = DiskCache("geocode", settings.geocode_cache_ttl)
forecast_cache = DiskCache("forecast", settings.forecast_cache_ttl)
