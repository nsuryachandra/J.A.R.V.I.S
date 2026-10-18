"""Unit tests for EventService: calendar events, RFC 5545 recurring routines, habit confirmations, and continuity."""

import uuid
from datetime import date, datetime, timedelta, timezone
import pytest
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.event import Event, Routine, RoutineConfirmation, RoutineOccurrence
from app.services.event_service import EventService


@pytest.mark.asyncio
async def test_one_time_event_lifecycle_and_invariants(db_session):
    """Verify one-time event creation, planned invariant, confirmation, and user isolation."""
    uid_a = uuid.uuid4()
    uid_b = uuid.uuid4()

    # Create planned event for User A
    event = await EventService.create_one_time_event(
        db=db_session,
        user_id=uid_a,
        title="Doctor Appointment",
        local_start="2026-10-25T10:30:00",
        local_end="2026-10-25T11:30:00",
        timezone_name="Asia/Kolkata",
        status="PLANNED",
    )
    assert event.id is not None
    assert event.title == "Doctor Appointment"
    assert event.status == "PLANNED"
    assert event.confirmed_at is None  # Invariant: Planned event is NOT confirmed
    assert event.timezone == "Asia/Kolkata"
    assert event.utc_start is not None

    # User A retrieves event
    fetched = await EventService.get_event(db_session, event.id, uid_a)
    assert fetched.id == event.id

    # User B cannot access User A's event
    with pytest.raises(PermissionDeniedError):
        await EventService.get_event(db_session, event.id, uid_b)

    with pytest.raises(PermissionDeniedError):
        await EventService.confirm_event(db_session, event.id, uid_b)

    # User A confirms event
    confirmed = await EventService.confirm_event(
        db_session,
        event.id,
        uid_a,
        notes="Attended appointment successfully",
    )
    assert confirmed.status == "COMPLETED"
    assert confirmed.confirmed_at is not None
    assert confirmed.notes == "Attended appointment successfully"


@pytest.mark.asyncio
async def test_one_time_event_validation_errors(db_session):
    """Verify input validation rules and error rejection."""
    uid = uuid.uuid4()

    # Empty title
    with pytest.raises(ValidationError, match="Event title cannot be empty"):
        await EventService.create_one_time_event(
            db=db_session,
            user_id=uid,
            title="   ",
            local_start="2026-10-25T10:00:00",
        )

    # Invalid timezone
    with pytest.raises(ValidationError, match="Invalid IANA timezone"):
        await EventService.create_one_time_event(
            db=db_session,
            user_id=uid,
            title="Meeting",
            local_start="2026-10-25T10:00:00",
            timezone_name="Mars/Base_Alpha",
        )

    # local_end before local_start
    with pytest.raises(ValidationError, match="local_end cannot be before local_start"):
        await EventService.create_one_time_event(
            db=db_session,
            user_id=uid,
            title="Meeting",
            local_start="2026-10-25T11:00:00",
            local_end="2026-10-25T10:00:00",
        )


@pytest.mark.asyncio
async def test_recurring_routine_creation_and_occurrence_expansion(db_session):
    """Verify routine creation, RFC 5545 expansion, deterministic SHA-256 keys, and initial PLANNED states."""
    uid = uuid.uuid4()

    # Create weekly routine on Mondays at 09:00
    routine = await EventService.create_routine(
        db=db_session,
        user_id=uid,
        title="Weekly Team Standup",
        recurrence_rule="FREQ=WEEKLY;BYDAY=MO",
        dtstart_local="2026-10-19T09:00:00",
        target_time="09:00:00",
        timezone_name="Asia/Kolkata",
        expand_days=30,
    )
    assert routine.id is not None
    assert routine.title == "Weekly Team Standup"
    assert routine.rule_version == 1
    assert routine.is_active is True
    assert routine.last_confirmed_at is None

    # Occurrences were expanded
    assert len(routine.occurrences) >= 4  # Roughly 4 Mondays in 30 days
    for occ in routine.occurrences:
        assert len(occ.occurrence_key) == 64  # SHA-256 identity key
        assert occ.status == "PLANNED"  # Invariant: Starts as PLANNED, NEVER COMPLETED!
        assert occ.last_check_in_at is None
        assert occ.confirmation is None


@pytest.mark.asyncio
async def test_invalid_recurrence_rule_rejected(db_session):
    """Verify that invalid RFC 5545 recurrence rules are caught and rejected."""
    uid = uuid.uuid4()

    with pytest.raises(ValidationError, match="Invalid RFC 5545 recurrence rule"):
        await EventService.create_routine(
            db=db_session,
            user_id=uid,
            title="Invalid Habit",
            recurrence_rule="NOT_A_VALID_RRULE",
            dtstart_local="2026-10-19T09:00:00",
        )


@pytest.mark.asyncio
async def test_occurrence_confirmation_and_check_in(db_session):
    """Verify check-in deduplication and explicit certification marking occurrence COMPLETED."""
    uid = uuid.uuid4()

    routine = await EventService.create_routine(
        db=db_session,
        user_id=uid,
        title="Intermittent Fasting",
        recurrence_rule="FREQ=DAILY",
        dtstart_local="2026-10-18T08:00:00",
        timezone_name="Asia/Kolkata",
        expand_days=7,
    )
    assert len(routine.occurrences) >= 7
    first_occ = routine.occurrences[0]
    assert first_occ.status == "PLANNED"

    # Step 1: Assistant performs proactive check-in ("How is your fasting going?")
    checked_in = await EventService.record_check_in(db_session, first_occ.id, uid)
    assert checked_in.last_check_in_at is not None
    assert checked_in.status == "PROMPTED"

    # Step 2: User explicitly confirms completion
    confirmed = await EventService.confirm_occurrence(
        db=db_session,
        occurrence_id=first_occ.id,
        user_id=uid,
        confirmed_by="user",
        notes="Fasted for 16 hours cleanly",
    )
    assert confirmed.status == "COMPLETED"
    assert confirmed.confirmation is not None
    assert confirmed.confirmation.confirmed_by == "user"
    assert confirmed.confirmation.notes == "Fasted for 16 hours cleanly"

    # Parent routine last_confirmed_at was updated
    refetched_routine = await EventService.get_routine(db_session, routine.id, uid)
    assert refetched_routine.last_confirmed_at is not None


@pytest.mark.asyncio
async def test_habit_query_continuity_and_accuracy(db_session):
    """
    Verify PRD Section 15.6 Habit Query ('When was my last {habit}?'):
    Accurately distinguishes confirmed past events from unconfirmed current routines.
    """
    uid = uuid.uuid4()

    # Case 1: No history, no routine
    query1 = await EventService.query_last_habit(db_session, uid, "fasting")
    assert query1["has_confirmed_history"] is False
    assert query1["has_active_routine"] is False
    assert "do not have a confirmed completed fasting day" in query1["formatted_message"]

    # Case 2: User adds an active recurring fasting routine, but has not confirmed any day yet
    routine = await EventService.create_routine(
        db=db_session,
        user_id=uid,
        title="Fasting Routine",
        recurrence_rule="FREQ=DAILY",
        dtstart_local="2026-10-18T08:00:00",
        timezone_name="Asia/Kolkata",
        expand_days=7,
    )
    query2 = await EventService.query_last_habit(db_session, uid, "fasting")
    assert query2["has_confirmed_history"] is False
    assert query2["has_active_routine"] is True
    assert "I have a fasting routine scheduled, but I do not have a confirmed completed" in query2["formatted_message"]

    # Case 3: A historical confirmed fasting event exists from last week
    historical_event = await EventService.create_one_time_event(
        db=db_session,
        user_id=uid,
        title="Fasting Day",
        local_start="2026-10-12T08:00:00",
        status="COMPLETED",
        notes="Confirmed completed fast",
    )
    query3 = await EventService.query_last_habit(db_session, uid, "fasting")
    assert query3["has_confirmed_history"] is True
    assert query3["has_active_routine"] is True
    assert query3["last_confirmed_type"] == "ONE_TIME_EVENT"
    assert "Your last confirmed fasting day was Monday, October 12, 2026" in query3["formatted_message"]
    assert "today's occurrence has not yet been confirmed" in query3["formatted_message"]

    # Case 4: Confirm today's occurrence
    # Find occurrence for today if present
    today_iso = date.today().isoformat()
    today_occ = None
    for o in routine.occurrences:
        if o.scheduled_date == today_iso:
            today_occ = o
            break

    if today_occ:
        await EventService.confirm_occurrence(db_session, today_occ.id, uid, notes="Done today")
        query4 = await EventService.query_last_habit(db_session, uid, "fasting")
        assert query4["has_confirmed_history"] is True
        assert query4["current_occurrence_status"] == "COMPLETED"
