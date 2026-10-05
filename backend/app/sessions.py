"""Journal routes for a private, single-owner deployment."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime

from app.config import settings
from app.forecast import get_forecast
from app.journal_models import ConditionSnapshot, MatchesResponse, SessionInput, SurfSession
from app.journal_store import JournalStore, spot_key
from app.session_matching import find_matches, has_required

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)


def get_store() -> JournalStore:
    return JournalStore(settings.journal_db_path)


async def resolve_snapshot(data: SessionInput):
    try:
        forecast = await get_forecast(data.location.latitude, data.location.longitude,
                                      data.location.timezone, data.location.name,
                                      data.location.country, data.location.country_code)
    except Exception:
        log.warning("Forecast unavailable while saving a session", exc_info=True)
        return None, "provider_unavailable"
    hour = data.session_at.replace(minute=0, second=0, microsecond=0)
    conditions = next((h for h in forecast.hourly if h.timestamp == hour), None)
    if conditions is None:
        return None, "hour_unavailable"
    providers = [p.model_copy(update={"hourly": [h for h in p.hourly if h.timestamp == hour]}) for p in forecast.providers]
    return ConditionSnapshot(captured_at=datetime.now(timezone.utc), generated_at=forecast.generated_at,
                             conditions=conditions, providers=providers,
                             notices=forecast.notices + forecast.warnings + forecast.errors), "available"


@router.get("/sessions", response_model=list[SurfSession])
def list_sessions(store: JournalStore = Depends(get_store)):
    return store.list()


@router.post("/sessions", response_model=SurfSession, status_code=201)
async def create_session(data: SessionInput, store: JournalStore = Depends(get_store)):
    snapshot, status = await resolve_snapshot(data)
    now = datetime.now(timezone.utc)
    session = SurfSession(**data.model_dump(), id=str(uuid4()), created_at=now, updated_at=now,
                          snapshot=snapshot, conditions_status=status)
    store.save(session)
    return session


@router.get("/sessions/{session_id}", response_model=SurfSession)
def get_session(session_id: str, store: JournalStore = Depends(get_store)):
    session = store.get(session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    return session


@router.put("/sessions/{session_id}", response_model=SurfSession)
async def update_session(session_id: str, data: SessionInput, store: JournalStore = Depends(get_store)):
    existing = get_session(session_id, store)
    snapshot, status = existing.snapshot, existing.conditions_status
    if (data.session_at != existing.session_at or
        (data.location.latitude, data.location.longitude) !=
        (existing.location.latitude, existing.location.longitude)):
        snapshot, status = await resolve_snapshot(data)
    session = SurfSession(**data.model_dump(), id=existing.id, created_at=existing.created_at,
                          updated_at=datetime.now(timezone.utc), snapshot=snapshot, conditions_status=status)
    if not store.save(session, update=True):
        raise HTTPException(404, "Session not found")
    return session


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str, store: JournalStore = Depends(get_store)):
    if not store.delete(session_id):
        raise HTTPException(404, "Session not found")
    return Response(status_code=204)


@router.get("/session-matches", response_model=MatchesResponse)
async def session_matches(hour: AwareDatetime, lat: float = Query(ge=-90, le=90),
                          lon: float = Query(ge=-180, le=180), store: JournalStore = Depends(get_store)):
    hour = hour.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    try:
        forecast = await get_forecast(lat, lon)
    except Exception:
        log.warning("Forecast unavailable for journal matching", exc_info=True)
        return MatchesResponse(hour=hour, status="provider_unavailable")
    target = next((h for h in forecast.hourly if h.timestamp == hour), None)
    if target is None:
        return MatchesResponse(hour=hour, status="hour_unavailable")
    if not has_required(target):
        return MatchesResponse(hour=hour, status="insufficient_conditions")
    # A report must already have happened by the forecast hour being compared.
    sessions = [s for s in store.list(spot_key(lat, lon)) if s.session_at.replace(minute=0, second=0, microsecond=0) <= hour]
    return MatchesResponse(hour=hour, status="available", matches=find_matches(sessions, target))
