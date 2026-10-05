"""Personal reports; observed values never overwrite modeled snapshots."""
from datetime import datetime, timezone
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models import GeoCandidate, HourlyConditions, ProviderSeries


class JournalLocation(GeoCandidate):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=200)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use a valid IANA timezone") from exc
        return value


class Observations(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    wave_height_m: float | None = Field(None, ge=0, le=50)
    wave_period_s: float | None = Field(None, gt=0, le=60)
    wave_direction_deg: float | None = Field(None, ge=0, lt=360)
    wind_speed_mps: float | None = Field(None, ge=0, le=150)
    wind_direction_deg: float | None = Field(None, ge=0, lt=360)
    tide_stage: Literal["low", "mid", "high", "unknown"] = "unknown"
    tide_movement: Literal["rising", "falling", "unknown"] = "unknown"


class SessionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    location: JournalLocation
    session_at: datetime
    note: str = Field(min_length=1, max_length=10000)
    rating: Literal["poor", "okay", "good", "great"]
    observations: Observations = Field(default_factory=Observations)

    @field_validator("note")
    @classmethod
    def nonblank_note(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Write a session note")
        return value

    @model_validator(mode="after")
    def normalize_time(self):
        value = self.session_at
        if value.tzinfo is None:
            # datetime-local controls send wall time at the selected spot.
            # During the repeated DST hour choose the earlier occurrence.
            zone = ZoneInfo(self.location.timezone)
            value = value.replace(tzinfo=zone, fold=0)
            if value.astimezone(timezone.utc).astimezone(zone).replace(tzinfo=None) != self.session_at:
                raise ValueError("This local time does not exist due to daylight saving time")
        self.session_at = value.astimezone(timezone.utc)
        if self.session_at > datetime.now(timezone.utc):
            raise ValueError("Session time cannot be in the future")
        return self


class ConditionSnapshot(BaseModel):
    captured_at: datetime
    generated_at: datetime
    conditions: HourlyConditions
    providers: list[ProviderSeries]
    notices: list[str] = Field(default_factory=list)


class SurfSession(SessionInput):
    id: str
    created_at: datetime
    updated_at: datetime
    snapshot: ConditionSnapshot | None = None
    conditions_status: Literal["available", "hour_unavailable", "provider_unavailable"]


class Comparison(BaseModel):
    field: str
    session_value: float
    forecast_value: float
    difference: float
    tolerance: float
    source: Literal["observed", "modeled"]


class SessionMatch(BaseModel):
    session: SurfSession
    distance: float
    comparisons: list[Comparison]


class MatchesResponse(BaseModel):
    hour: datetime
    status: Literal["available", "hour_unavailable", "provider_unavailable", "insufficient_conditions"]
    matches: list[SessionMatch] = Field(default_factory=list)
