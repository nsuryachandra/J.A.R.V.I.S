"""Tests for OneTimeEvent, RecurringRoutine, RoutineOccurrence, and EventCompletion."""

from datetime import datetime, timezone
import uuid
import pytest
from pydantic import ValidationError
from app.contracts.events import (
    EventCompletion,
    EventConfirmation,
    EventException,
    OneTimeEvent,
    RecurringRoutine,
    RoutineOccurrence,
)
from app.temporal.identity import OccurrenceIdentityGenerator
from app.temporal.schemas import EventState


def test_one_time_event_timezone_and_instant():
    """Verify OneTimeEvent stores normalized UTC instant and preserves original timezone."""
    uid = uuid.uuid4()
    utc_instant = datetime(2026, 10, 19, 8, 30, 0, tzinfo=timezone.utc)
    event = OneTimeEvent(
        user_id=uid,
        title="Dentist Appointment",
        local_date_time="2026-10-19T14:00:00+05:30",
        utc_instant=utc_instant,
        timezone="Asia/Kolkata",
    )
    assert event.user_id == uid
    assert event.state == EventState.PLANNED
    assert event.timezone == "Asia/Kolkata"
    assert event.utc_instant == utc_instant


def test_recurring_routine_contract():
    """Verify RecurringRoutine stores RFC 5545 rule and local start parameters."""
    uid = uuid.uuid4()
    routine = RecurringRoutine(
        user_id=uid,
        title="Morning Fasting",
        rule_version=1,
        rrule="FREQ=WEEKLY;BYDAY=MO",
        dtstart_local="2026-10-19T06:00:00",
        timezone="Asia/Kolkata",
    )
    assert routine.user_id == uid
    assert routine.rule_version == 1
    assert routine.rrule == "FREQ=WEEKLY;BYDAY=MO"
    assert routine.is_active is True


def test_routine_occurrence_lifecycle():
    """Verify that a generated occurrence starts as PLANNED and cannot be COMPLETED without completion proof."""
    rid = uuid.uuid4()
    utc_instant = datetime(2026, 10, 19, 0, 30, 0, tzinfo=timezone.utc)
    occ_key = OccurrenceIdentityGenerator.generate_key(
        routine_id=rid,
        rule_version=1,
        local_date_time="2026-10-19T06:00:00+05:30",
        timezone="Asia/Kolkata",
        sequence_index=1,
    )

    occ = RoutineOccurrence(
        occurrence_key=occ_key,
        routine_id=rid,
        sequence_index=1,
        local_time="2026-10-19T06:00:00+05:30",
        utc_instant=utc_instant,
        timezone="Asia/Kolkata",
    )
    assert occ.state == EventState.PLANNED
    assert occ.completion is None

    # Setting COMPLETED without completion record fails
    with pytest.raises(ValidationError) as exc:
        RoutineOccurrence(
            occurrence_key=occ_key,
            routine_id=rid,
            sequence_index=1,
            state=EventState.COMPLETED,
            local_time="2026-10-19T06:00:00+05:30",
            utc_instant=utc_instant,
            timezone="Asia/Kolkata",
        )
    assert "cannot be COMPLETED without an explicit EventCompletion record" in str(exc.value)

    # With EventCompletion record, COMPLETED succeeds
    conf = EventConfirmation(
        occurrence_key=occ_key,
        confirmed_by="user",
        notes="User stated: 'I completed my fasting today'",
    )
    completion = EventCompletion(
        occurrence_key=occ_key,
        confirmation=conf,
    )
    occ_completed = RoutineOccurrence(
        occurrence_key=occ_key,
        routine_id=rid,
        sequence_index=1,
        state=EventState.COMPLETED,
        local_time="2026-10-19T06:00:00+05:30",
        utc_instant=utc_instant,
        timezone="Asia/Kolkata",
        completion=completion,
    )
    assert occ_completed.state == EventState.COMPLETED
    assert occ_completed.completion.confirmation.confirmed_by == "user"
