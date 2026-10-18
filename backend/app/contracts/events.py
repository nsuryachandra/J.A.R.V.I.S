"""Domain contracts for calendar events, recurring routines, and occurrence confirmations."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    UserScopedResource,
    VersionedContract,
)
from app.temporal.schemas import EventState, OccurrenceIdentity


class OccurrenceReference(BaseModel):
    """Reference coordinates to a specific occurrence of a routine."""

    model_config = ConfigDict(frozen=True)

    occurrence_key: str = Field(min_length=64, max_length=64, description="Phase 3 SHA-256 occurrence identity")
    routine_id: UUID
    rule_version: int
    local_date_time: str
    timezone: str


class EventConfirmation(BaseModel):
    """Explicit human or sensor certification that an occurrence took place."""

    model_config = ConfigDict(frozen=True)

    confirmation_id: UUID = Field(default_factory=uuid4)
    occurrence_key: str = Field(min_length=64, max_length=64)
    confirmed_by: str = Field(description="Actor certifying confirmation")
    confirmed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    notes: Optional[str] = None


class EventCompletion(BaseModel):
    """Certified historical completion record for an occurrence."""

    model_config = ConfigDict(frozen=True)

    completion_id: UUID = Field(default_factory=uuid4)
    occurrence_key: str = Field(min_length=64, max_length=64)
    completed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    confirmation: EventConfirmation


class EventException(BaseModel):
    """Exclusion definition for a recurring routine (e.g. holiday or skip)."""

    model_config = ConfigDict(frozen=True)

    exception_id: UUID = Field(default_factory=uuid4)
    routine_id: UUID
    exception_date_local: str = Field(description="Local date string e.g. YYYY-MM-DD")
    reason: str = Field(min_length=1, max_length=512)


class EventStateTransition(BaseModel):
    """Audit record capturing an explicit transition across lifecycle states."""

    model_config = ConfigDict(frozen=True)

    occurrence_key: str = Field(min_length=64, max_length=64)
    from_state: EventState
    to_state: EventState
    transitioned_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    reason: str


class OneTimeEvent(UserScopedResource):
    """Singular calendar event scheduled at a discrete point in time."""

    contract_type: str = Field(default="event.one_time")
    event_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=255)
    state: EventState = Field(default=EventState.PLANNED)
    local_date_time: str = Field(description="Local ISO string in event timezone")
    utc_instant: datetime = Field(description="Normalized UTC instant")
    timezone: str = Field(description="Original IANA timezone")
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.PERSONAL)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)

    @field_validator("utc_instant")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("utc_instant must be a timezone-aware UTC datetime")
        return v.astimezone(timezone.utc)


class RecurringRoutine(UserScopedResource):
    """Standing schedule rule that generates discrete occurrences."""

    contract_type: str = Field(default="event.recurring_routine")
    routine_id: UUID = Field(default_factory=uuid4)
    title: str = Field(min_length=1, max_length=255)
    rule_version: int = Field(default=1, ge=1)
    rrule: str = Field(description="RFC 5545 recurrence rule string")
    dtstart_local: str = Field(description="Start time in routine's local calendar")
    timezone: str = Field(description="Home IANA timezone for calendar evaluation")
    is_active: bool = Field(default=True)
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.PERSONAL)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)


class RoutineOccurrence(VersionedContract):
    """Single discrete occurrence derived from a recurring routine."""

    contract_type: str = Field(default="event.routine_occurrence")
    occurrence_key: str = Field(min_length=64, max_length=64)
    routine_id: UUID
    sequence_index: int = Field(ge=1)
    state: EventState = Field(
        default=EventState.PLANNED,
        description="A generated occurrence starts as PLANNED, never COMPLETED",
    )
    local_time: str
    utc_instant: datetime
    timezone: str
    completion: Optional[EventCompletion] = None

    @model_validator(mode="after")
    def validate_occurrence_completion_rule(self) -> "RoutineOccurrence":
        # A routine occurrence cannot be COMPLETED without explicit EventCompletion
        if self.state == EventState.COMPLETED and self.completion is None:
            raise ValueError(
                "A RoutineOccurrence cannot be COMPLETED without an explicit EventCompletion record."
            )
        return self
