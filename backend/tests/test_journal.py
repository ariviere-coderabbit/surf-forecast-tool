from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.journal_models import SessionInput, SurfSession
from app.journal_store import JournalStore, spot_key
from app.models import ForecastResponse, GeoCandidate, HourlyConditions, SpotProfile
from app.session_matching import find_matches

LOCATION = dict(id=1, name="Jacó", country="Costa Rica", country_code="CR",
                latitude=9.613, longitude=-84.628, timezone="America/Costa_Rica")
HOUR = datetime(2024, 1, 15, 12, tzinfo=timezone.utc)


def payload(**updates):
    return {"location": LOCATION, "session_at": "2024-01-15T06:30",
            "note": "Clean waves. Great day!", "rating": "great", "observations": {}, **updates}


def forecast():
    return ForecastResponse(location=GeoCandidate(**LOCATION),
        spot_profile=SpotProfile(name="Jacó", latitude=9.613, longitude=-84.628),
        generated_at=HOUR,
        hourly=[HourlyConditions(timestamp=HOUR, wave_height_m=1.2, wave_period_s=10,
                                wave_direction_deg=355, wind_speed_mps=3, wind_direction_deg=90)], providers=[])


@pytest.fixture
def journal(tmp_path, monkeypatch):
    monkeypatch.setattr("app.sessions.settings.journal_db_path", tmp_path / "journal.sqlite3")
    fetch = AsyncMock(return_value=forecast())
    monkeypatch.setattr("app.sessions.get_forecast", fetch)
    return tmp_path / "journal.sqlite3", fetch


@pytest.mark.anyio
async def test_create_persist_read_edit_delete(client, journal):
    path, fetch = journal
    response = await client.post("/api/sessions", json=payload())
    assert response.status_code == 201
    saved = response.json()
    assert saved["session_at"] == "2024-01-15T12:30:00Z"
    assert saved["snapshot"]["conditions"]["timestamp"] == "2024-01-15T12:00:00Z"
    assert saved["snapshot"]["conditions"]["wave_height_m"] == 1.2
    session_id = saved["id"]
    # New connection/store represents reopening the database after restart.
    assert JournalStore(path).get(session_id).note == payload()["note"]
    assert len((await client.get("/api/sessions")).json()) == 1
    assert (await client.get(f"/api/sessions/{session_id}")).json() == saved
    updated = await client.put(f"/api/sessions/{session_id}", json=payload(note="Actually just okay", rating="okay", observations={"wave_height_m": 2}))
    assert updated.status_code == 200
    assert updated.json()["snapshot"] == saved["snapshot"]
    assert updated.json()["observations"]["wave_height_m"] == 2
    assert fetch.await_count == 1
    assert (await client.delete(f"/api/sessions/{session_id}")).status_code == 204
    assert JournalStore(path).get(session_id) is None
    assert (await client.get(f"/api/sessions/{session_id}")).status_code == 404
    assert (await client.put(f"/api/sessions/{session_id}", json=payload())).status_code == 404
    assert (await client.delete(f"/api/sessions/{session_id}")).status_code == 404


@pytest.mark.anyio
async def test_corrected_time_and_location_resolve_new_snapshot(client, journal):
    _, fetch = journal
    saved = (await client.post("/api/sessions", json=payload())).json()
    update = await client.put(f'/api/sessions/{saved["id"]}', json=payload(session_at="2020-01-01T06:00"))
    assert update.json()["snapshot"] is None
    assert update.json()["conditions_status"] == "hour_unavailable"
    await client.put(f'/api/sessions/{saved["id"]}', json=payload(location={**LOCATION, "latitude": 1}))
    assert fetch.await_count == 3


@pytest.mark.anyio
async def test_unavailable_provider_and_historical_hour_still_save(client, journal):
    _, fetch = journal
    fetch.side_effect = RuntimeError("provider offline")
    response = await client.post("/api/sessions", json=payload())
    assert response.status_code == 201
    assert response.json()["conditions_status"] == "provider_unavailable"
    fetch.side_effect = None
    response = await client.post("/api/sessions", json=payload(session_at="2020-01-01T06:00"))
    assert response.status_code == 201
    assert response.json()["snapshot"] is None
    assert response.json()["conditions_status"] == "hour_unavailable"


@pytest.mark.parametrize("changes", [
    {"note": "   "}, {"rating": "excellent"}, {"session_at": "2099-01-01T00:00:00Z"},
    {"location": {**LOCATION, "latitude": 100}}, {"location": {**LOCATION, "timezone": "invalid"}},
    {"observations": {"wind_speed_mps": -1}}, {"observations": {"wave_direction_deg": 360}},
    {"observations": {"tide_stage": "huge"}}, {"observations": {"wave_period_s": 0}},
    {"snapshot": {}},
])
@pytest.mark.anyio
async def test_invalid_input(client, journal, changes):
    assert (await client.post("/api/sessions", json=payload(**changes))).status_code == 422


def test_timezone_dst_conversion():
    location = {**LOCATION, "timezone": "America/New_York"}
    early = SessionInput(**payload(location=location, session_at="2024-11-03T01:30"))
    assert early.session_at.isoformat() == "2024-11-03T05:30:00+00:00"
    explicit = SessionInput(**payload(location=location, session_at="2024-11-03T01:30:00-05:00"))
    assert explicit.session_at.hour == 6
    with pytest.raises(ValidationError, match="does not exist"):
        SessionInput(**payload(location=location, session_at="2024-03-10T02:30"))


@pytest.mark.anyio
async def test_matches_include_current_hour_report_and_refresh_on_changes(client, journal):
    saved = (await client.post("/api/sessions", json=payload())).json()
    params = dict(lat=9.613, lon=-84.628, hour=HOUR.isoformat())
    result = (await client.get("/api/session-matches", params=params)).json()
    assert result["matches"][0]["session"]["id"] == saved["id"]
    assert result["matches"][0]["distance"] == 0
    # Another spot does not share the generic profile's reports.
    assert (await client.get("/api/session-matches", params={**params, "lat": 9.614})).json()["matches"] == []
    await client.put(f'/api/sessions/{saved["id"]}', json=payload(rating="poor"))
    assert (await client.get("/api/session-matches", params=params)).json()["matches"][0]["session"]["rating"] == "poor"
    await client.delete(f'/api/sessions/{saved["id"]}')
    assert (await client.get("/api/session-matches", params=params)).json()["matches"] == []


@pytest.mark.anyio
async def test_match_availability_and_aware_hour(client, journal):
    _, fetch = journal
    params = dict(lat=9.613, lon=-84.628, hour="2020-01-01T00:00:00Z")
    assert (await client.get("/api/session-matches", params=params)).json()["status"] == "hour_unavailable"
    params["hour"] = HOUR.isoformat()
    fetch.return_value.hourly[0].wave_period_s = None
    assert (await client.get("/api/session-matches", params=params)).json()["status"] == "insufficient_conditions"
    fetch.side_effect = RuntimeError("offline")
    assert (await client.get("/api/session-matches", params=params)).json()["status"] == "provider_unavailable"
    params["hour"] = "2020-01-01T00:00"
    assert (await client.get("/api/session-matches", params=params)).status_code == 422


def observed_session(index=1, **observations):
    return SurfSession(**payload(observations={"wave_height_m": 1.2, "wave_period_s": 10,
                                               "wind_speed_mps": 3, **observations}),
                       id=str(index), created_at=HOUR, updated_at=HOUR, conditions_status="hour_unavailable")


def test_matching_boundaries_directions_missing_values_and_limit():
    target = forecast().hourly[0]
    boundary = observed_session(wave_height_m=1.7, wave_period_s=12, wind_speed_mps=5, wave_direction_deg=40)
    assert len(find_matches([boundary], target)) == 1
    assert find_matches([observed_session(wave_height_m=1.701)], target) == []
    assert find_matches([observed_session(wave_direction_deg=41)], target) == []
    wrap = find_matches([observed_session(wave_direction_deg=5)], target)
    assert next(c for c in wrap[0].comparisons if c.field == "wave_direction_deg").difference == 10
    assert find_matches([observed_session(wave_height_m=None)], target) == []
    target.wind_speed_mps = None
    assert find_matches([boundary], target) == []
    matches = find_matches([observed_session(i) for i in range(5)], forecast().hourly[0])
    assert len(matches) == 3
    assert all(c.source == "observed" for c in matches[0].comparisons)


@pytest.mark.anyio
async def test_observations_override_model_for_matching_without_modifying_snapshot(client, journal):
    saved = (await client.post("/api/sessions", json=payload(observations={"wave_height_m": 4, "tide_stage": "high"}))).json()
    assert saved["snapshot"]["conditions"]["wave_height_m"] == 1.2
    assert find_matches([SurfSession(**saved)], forecast().hourly[0]) == []


def test_store_schema_version_and_signed_zero(tmp_path):
    assert spot_key(0, -0.0) == spot_key(-0.0, 0)
    path = tmp_path / "journal.sqlite3"
    store = JournalStore(path)
    with store.connect() as db:
        db.execute("PRAGMA user_version = 2")
    with pytest.raises(RuntimeError, match="newer"):
        JournalStore(path)


@pytest.mark.anyio
async def test_cors_allows_journal_writes(client):
    result = await client.options("/api/sessions", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert result.status_code == 200
