"""Temporal resolver facade coordinating parsing, timezone awareness, recurrence, and event states."""

from datetime import datetime, timezone as dt_timezone
from typing import List, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ValidationError
from app.models.user import User
from app.services.audit_service import AuditService
from app.temporal.identity import OccurrenceIdentityGenerator
from app.temporal.parser import TemporalParser
from app.temporal.recurrence import RecurrenceService
from app.temporal.schemas import (
    EventState,
    OccurrenceIdentity,
    RecurrenceOccurrence,
    TemporalResolution,
    TemporalResolutionStatus,
)
from app.temporal.timezone import TimezoneService, UTC


class EventStateMachine:
    """Deterministic event-state transition rules."""

    ALLOWED_TRANSITIONS = {
        EventState.PLANNED: {
            EventState.CONFIRMED,
            EventState.COMPLETED,
            EventState.MISSED,
            EventState.CANCELLED,
            EventState.SKIPPED,
            EventState.EXPIRED,
        },
        EventState.CONFIRMED: {
            EventState.COMPLETED,
            EventState.MISSED,
            EventState.CANCELLED,
            EventState.SKIPPED,
        },
        EventState.UNKNOWN: {
            EventState.PLANNED,
            EventState.CONFIRMED,
            EventState.COMPLETED,
            EventState.MISSED,
            EventState.CANCELLED,
            EventState.SKIPPED,
        },
        EventState.COMPLETED: set(),  # Terminal state
        EventState.MISSED: {EventState.COMPLETED},  # Retrospective completion allowed if confirmed
        EventState.CANCELLED: set(),  # Terminal state
        EventState.EXPIRED: set(),  # Terminal state
        EventState.SKIPPED: set(),  # Terminal state
    }

    @classmethod
    def can_transition(cls, from_state: EventState, to_state: EventState) -> bool:
        """Validate whether a state transition is permitted."""
        if from_state == to_state:
            return True
        allowed = cls.ALLOWED_TRANSITIONS.get(from_state, set())
        return to_state in allowed

    @classmethod
    def transition(cls, from_state: EventState, to_state: EventState) -> EventState:
        """Execute state transition or raise ValidationError."""
        if not cls.can_transition(from_state, to_state):
            raise ValidationError(
                f"Illegal temporal event state transition from {from_state.value} to {to_state.value}"
            )
        return to_state


class TemporalService:
    """High-level temporal engine orchestrating parsing, recurrence, identity, and timezone normalization."""

    @classmethod
    def resolve_expression(
        cls,
        text: str,
        user: Optional[User] = None,
        reference_time_utc: Optional[datetime] = None,
        timezone_override: Optional[str] = None,
    ) -> TemporalResolution:
        """
        Resolve natural language temporal expression with authenticated user context.
        Derives timezone from user, validating against IANA database.
        """
        # Determine effective timezone
        if timezone_override:
            tz = TimezoneService.validate_or_raise(timezone_override).key
        elif user and user.timezone:
            tz = TimezoneService.get_effective_timezone(user.timezone)
        else:
            tz = TimezoneService.get_effective_timezone(None)

        resolution = TemporalParser.resolve(
            text=text,
            reference_time_utc=reference_time_utc,
            timezone=tz,
            user_id=user.id if user else None,
        )
        return resolution

    @classmethod
    def expand_recurrence(
        cls,
        routine_id: UUID | str,
        rule_version: int,
        rrule_string: str,
        dtstart_local: str | datetime,
        timezone: Optional[str] = None,
        max_occurrences: int = 100,
        window_start_utc: Optional[datetime] = None,
        window_end_utc: Optional[datetime] = None,
        exdates: Optional[List[str]] = None,
    ) -> List[RecurrenceOccurrence]:
        """Expand recurrence rule into discrete occurrences with immutable identity hashes."""
        return RecurrenceService.expand_recurrence(
            routine_id=routine_id,
            rule_version=rule_version,
            rrule_string=rrule_string,
            dtstart_local=dtstart_local,
            timezone=timezone,
            max_occurrences=max_occurrences,
            window_start_utc=window_start_utc,
            window_end_utc=window_end_utc,
            exdates=exdates,
        )

    @classmethod
    def generate_occurrence_identity(
        cls,
        routine_id: UUID | str,
        rule_version: int,
        local_date_time: str,
        timezone: str,
        sequence_index: Optional[int] = None,
    ) -> OccurrenceIdentity:
        """Create deterministic occurrence key."""
        return OccurrenceIdentityGenerator.create_identity(
            routine_id=routine_id,
            rule_version=rule_version,
            local_date_time=local_date_time,
            timezone=timezone,
            sequence_index=sequence_index,
        )

    @classmethod
    def preserve_utc_on_timezone_change(
        cls,
        utc_instant: datetime,
        new_timezone: str,
    ) -> tuple[datetime, str]:
        """
        When user changes timezone:
        Preserves the absolute point in time (UTC instant unchanged) while computing new local display.
        """
        TimezoneService.validate_or_raise(new_timezone)
        aware_utc = TimezoneService.to_utc(utc_instant)
        new_local = TimezoneService.to_local(aware_utc, new_timezone)
        return aware_utc, TimezoneService.format_local_iso(new_local, new_timezone)
