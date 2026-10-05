# Surf Forecast Tool

Surf forecast for Jacó, Costa Rica (and a generic fallback for other locations), powered by Open-Meteo and NOAA/NCEP GFS-Wave. No API keys or accounts required.

---

## Frontend setup

### Prerequisites

- Node.js 20.19+ or 22.12+ (Node 24 recommended) and npm

### Install and run (development)

```bash
cd frontend
npm ci
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

- Wave forecasts: [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api) (DWD GWAM, DWD) and [NOAA/NCEP GFS-Wave 0.16°](https://nomads.ncep.noaa.gov/)
- Wind: [Open-Meteo Forecast API](https://open-meteo.com/en/docs)
- Geocoding: [Open-Meteo Geocoding API](https://open-meteo.com/en/docs/geocoding-api)

All sources are free and available for non-commercial use.


## Personal surf journal

Use **Log a session** to save your own words, a Poor/Okay/Good/Great rating,
location, and session time. **Observed conditions** optionally captures wind,
waves, and tide. You can also log a session when forecast providers are unavailable.
Open **Journal** to review, edit, or delete reports.

Session times use the selected location's timezone and are stored in UTC. Past
sessions are supported; future session reports are rejected. For daylight-saving
transitions, nonexistent local times are rejected and repeated local times use the
earlier occurrence (API callers can provide an explicit UTC offset).

Available modeled conditions for the session's exact UTC hour are copied into the
report, together with provider metadata and capture time. No historical weather
backfill is performed: if that hour is unavailable, the note and observations are
still saved. Editing text, rating, or observations preserves the original snapshot;
changing session time or coordinates resolves a replacement snapshot.

### Storage and deployment

This version is for **one owner on a private backend**. There is no account system;
anyone with access to the backend can read and modify its journal. All devices
using that backend share the same journal. Do not expose it as a public service.

SQLite defaults to `backend/data/journal.sqlite3`. Set `JOURNAL_DB_PATH` to a path
on a persistent volume for deployment. The parent directory must be writable.
Database files are ignored by Git and are independent of forecast cache cleanup.
Back up the journal using SQLite's backup API (or copy the file while the backend
is stopped). Keep backups private. Schema version 1 is initialized automatically;
the app refuses to open a database from a newer schema version.

### Learnings alongside the forecast

**Similar sessions from your journal** compares a selected forecast hour against
reports at the same coordinates rounded to four decimal places. It includes both
good and bad outcomes and displays up to three closest sessions, original notes,
and condition differences. Existing surfability scores remain unchanged.

Wave height, wave period, and wind speed are required on both sides. Optional
wave/wind directions and modeled sea level also constrain matches when present.
Explicit wave/wind observations take precedence for comparisons; modeled
snapshots remain unchanged. Tide stage is context only: modeled sea level is not
a tide prediction. Similar conditions do not guarantee a similar experience.

Initial tolerances are configurable through environment variables:

| Variable | Default |
|---|---:|
| `MATCH_HEIGHT_M` | 0.5 |
| `MATCH_PERIOD_S` | 2 |
| `MATCH_WIND_MPS` | 2 |
| `MATCH_DIRECTION_DEG` | 45 |
| `MATCH_SEA_LEVEL_M` | 0.3 |

All compared fields must fall within tolerance. Matches are ranked by the mean
of differences divided by their tolerances, with newer sessions breaking ties.
Directions use circular differences. Missing optional values are not compared.
These are initial heuristics, not calibrated predictions.

### Journal API

- `POST /api/sessions`: create a report; returns 201 and the saved report.
- `GET /api/sessions`: list reports newest first.
- `GET /api/sessions/{id}`: read a report.
- `PUT /api/sessions/{id}`: replace editable report fields.
- `DELETE /api/sessions/{id}`: delete a report; returns 204.
- `GET /api/session-matches?lat=...&lon=...&hour=...`: compare an offset-aware
  forecast timestamp; returns availability status and matched reports.

Create/update accepts `location` (the geocoding candidate), `session_at` (ISO time,
interpreted in the location timezone if no offset is supplied), `note`, `rating`,
and optional `observations`. Snapshots are resolved by the server, not accepted
from the client. Full request/response schemas are available at backend `/docs`.
