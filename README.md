# Surf Forecast Tool

Surf forecast for Jacó, Costa Rica (and generic fallback for other locations), using free public data from Open-Meteo and NOAA/NCEP.

**Data sources:** Open-Meteo Marine (ICON-Wave), Open-Meteo Forecast (wind), NOAA NCEP GFS-Wave 0.16°  
**No accounts, API keys, or paid services required.**

---

## Backend setup

### Prerequisites

- Python 3.11+
- [ecCodes](https://confluence.ecmwf.int/display/ECC/ecCodes+installation) — required for NOAA GRIB2 decoding

Install ecCodes on macOS:
```bash
brew install eccodes
```

On Ubuntu/Debian:
```bash
sudo apt-get install libeccodes-dev
```

### Install

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # includes test deps
# or for production only:
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env if you want to change cache locations or NOAA region
```

### Run (development)

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

API available at `http://localhost:8000`:
- `GET /api/health`
- `GET /api/geocode?q=Jaco%2C+Costa+Rica`
- `GET /api/forecast?lat=9.613&lon=-84.628&name=Jac%C3%B3&timezone=America%2FCosta_Rica`

### Run tests

```bash
cd backend
source .venv/bin/activate
pytest
```

---

## Frontend setup

*(Frontend not yet implemented — see frontend/ directory after the next step.)*

---

## Caveats and notices

- **Surfability scores** are heuristic and explicitly uncalibrated. They are not a substitute for local knowledge.
- **Jacó profile** is approximate; no field calibration has been done.
- **Sea level** from Open-Meteo is modeled output, not a tide table.
- **NOAA GFS-Wave** data is fetched in the background every 6 hours. The first forecast may not include NOAA data until the background refresh completes.
- **Sampling distance** is shown for each provider so you can judge grid-point proximity to your location.

---

## Architecture

```
backend/
  app/
    main.py           FastAPI routes and lifespan
    config.py         Environment-based settings
    models.py         Pydantic models
    geocoding.py      Open-Meteo geocoding (24 h cache)
    merger.py         Multi-provider merge (circular directions, no interpolation)
    scorer.py         Surfability scoring heuristics
    spot_profiles.py  Jacó profile + generic fallback
    cache.py          Disk-based JSON cache
    adapters/
      open_meteo_waves.py    ICON-Wave via Marine API
      open_meteo_wind.py     Wind via Forecast API
      open_meteo_sealevel.py Modeled sea level (best-effort)
      noaa_gfswave.py        GFS-Wave 0.16° via NOMADS filter + eccodes
  tests/
    test_geocoding.py
    test_merger.py
    test_scorer.py
    test_adapters.py
    test_api.py
```
