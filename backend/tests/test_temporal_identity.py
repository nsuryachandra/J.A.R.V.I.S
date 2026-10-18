"""Tests for OccurrenceIdentityGenerator and EventStateMachine."""

import uuid
import pytest
from app.core.exceptions import ValidationError
from app.temporal.identity import OccurrenceIdentityGenerator
from app.temporal.resolver import EventStateMachine
from app.temporal.schemas import EventState


def test_occurrence_key_stability():
    """Verify identical parameters produce exactly identical SHA-256 keys."""
    rid = uuid.uuid4()
    key1 = OccurrenceIdentityGenerator.generate_key(
        routine_id=rid,
        rule_version=1,
        local_date_time="2026-10-19T08:00:00+05:30",
        timezone="Asia/Kolkata",
        sequence_index=1,
    )
    key2 = OccurrenceIdentityGenerator.generate_key(
        routine_id=rid,
        rule_version=1,
        local_date_time="2026-10-19T08:00:00+05:30",
        timezone="Asia/Kolkata",
        sequence_index=1,
    )

    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex string


def test_occurrence_key_sensitivity():
    """Verify changing any input dimension strictly alters the SHA-256 key."""
    rid1 = uuid.uuid4()
    rid2 = uuid.uuid4()
    base_params = {
        "routine_id": rid1,
        "rule_version": 1,
        "local_date_time": "2026-10-19T08:00:00+05:30",
        "timezone": "Asia/Kolkata",
        "sequence_index": 1,
    }

    base_key = OccurrenceIdentityGenerator.generate_key(**base_params)

    # Change routine ID
    p_rid = dict(base_params, routine_id=rid2)
    assert OccurrenceIdentityGenerator.generate_key(**p_rid) != base_key

    # Change rule version
    p_ver = dict(base_params, rule_version=2)
    assert OccurrenceIdentityGenerator.generate_key(**p_ver) != base_key

    # Change local datetime
    p_dt = dict(base_params, local_date_time="2026-10-20T08:00:00+05:30")
    assert OccurrenceIdentityGenerator.generate_key(**p_dt) != base_key

    # Change timezone
    p_tz = dict(base_params, timezone="UTC")
    assert OccurrenceIdentityGenerator.generate_key(**p_tz) != base_key


def test_event_state_machine_valid_transitions():
    """Verify permitted lifecycle transitions."""
    # PLANNED -> CONFIRMED
    assert EventStateMachine.transition(EventState.PLANNED, EventState.CONFIRMED) == EventState.CONFIRMED
    # CONFIRMED -> COMPLETED
    assert EventStateMachine.transition(EventState.CONFIRMED, EventState.COMPLETED) == EventState.COMPLETED
    # PLANNED -> MISSED
    assert EventStateMachine.transition(EventState.PLANNED, EventState.MISSED) == EventState.MISSED
    # MISSED -> COMPLETED (retrospective confirmation)
    assert EventStateMachine.transition(EventState.MISSED, EventState.COMPLETED) == EventState.COMPLETED
    # PLANNED -> SKIPPED
    assert EventStateMachine.transition(EventState.PLANNED, EventState.SKIPPED) == EventState.SKIPPED


def test_event_state_machine_illegal_transitions():
    """Verify illegal transitions are rejected."""
    # COMPLETED is terminal
    assert EventStateMachine.can_transition(EventState.COMPLETED, EventState.PLANNED) is False
    with pytest.raises(ValidationError):
        EventStateMachine.transition(EventState.COMPLETED, EventState.PLANNED)

    # CANCELLED is terminal
    with pytest.raises(ValidationError):
        EventStateMachine.transition(EventState.CANCELLED, EventState.COMPLETED)
