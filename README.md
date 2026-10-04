# Surf Forecast Tool

Surf forecast for Jacó, Costa Rica (and a generic fallback for other locations), powered by Open-Meteo and NOAA/NCEP GFS-Wave. No API keys or accounts required.

---

## Frontend setup

### Prerequisites

- Node.js 18+ and npm

### Install and run (development)

```bash
cd frontend
npm install
npm run dev          # starts on http://localhost:5173
```

The Vite dev server proxies `/api/*` requests to the FastAPI backend on `:8000`. Start the backend first (see below).

### Run tests

```bash
cd frontend
npm test             # Vitest in watch mode
npm test -- --run    # single-pass for CI
```

### Production build

```bash
cd frontend
npm run build        # outputs to frontend/dist/
```

---

## Backend setup

### Prerequisites

- Python 3.11+
- [ecCodes](https://confluence.ecmwf.int/display/ECC/ecCodes+installation) for NOAA GRIB2 decoding

```bash
# macOS
brew install eccodes

# Ubuntu/Debian
sudo apt-get install libeccodes-dev
```

### Install and run

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # edit if needed
uvicorn app.main:app --reload --port 8000
```

### Run tests

```bash
cd backend
source .venv/bin/activate
pytest
```

---

## API endpoints

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service health check |
| `GET /api/geocode?q=Jacó` | Resolve location; returns candidates |
| `GET /api/forecast?lat=9.613&lon=-84.628&timezone=America/Costa_Rica` | Full forecast |

---

## Caveats

- **Surfability scores** are heuristic and uncalibrated — not a substitute for local knowledge.
- **Jacó profile** is approximate; no field calibration done.
- **Sea level** from Open-Meteo is modeled output, not a tide table.
- **NOAA GFS-Wave** data is fetched in the background every 6 hours; first request may not include it.
- **Sampling distance** is shown for each provider — larger distances mean lower local accuracy.

## Data attribution

- Wave forecasts: [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api) (ICON-Wave, DWD) and [NOAA/NCEP GFS-Wave 0.16°](https://nomads.ncep.noaa.gov/)
- Wind: [Open-Meteo Forecast API](https://open-meteo.com/en/docs)
- Geocoding: [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)

All sources are free and available for non-commercial use.
