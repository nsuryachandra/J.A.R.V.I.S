"""Tests for RFC 5545 RecurrenceService: daily, weekly, multi-day, monthly, COUNT, UNTIL, EXDATE."""

from datetime import datetime
import uuid
import pytest
from app.core.exceptions import ValidationError
from app.temporal.recurrence import RecurrenceService


ROUTINE_ID = uuid.uuid4()
RULE_VERSION = 1
DEFAULT_TZ = "Asia/Kolkata"


def test_daily_recurrence():
    """Verify daily recurrence expansion."""
    occurrences = RecurrenceService.expand_recurrence(
        routine_id=ROUTINE_ID,
        rule_version=RULE_VERSION,
        rrule_string="FREQ=DAILY",
        dtstart_local="2026-10-19T08:00:00",
        timezone=DEFAULT_TZ,
        max_occurrences=5,
    )

    assert len(occurrences) == 5
    assert occurrences[0].local_time.startswith("2026-10-19T08:00:00")
    assert occurrences[1].local_time.startswith("2026-10-20T08:00:00")
    assert occurrences[2].local_time.startswith("2026-10-21T08:00:00")
    assert occurrences[3].local_time.startswith("2026-10-22T08:00:00")
    assert occurrences[4].local_time.startswith("2026-10-23T08:00:00")

    # Verify UTC conversion (08:00 IST -> 02:30 UTC)
    for occ in occurrences:
        assert occ.utc_instant.endswith("02:30:00Z")
        assert len(occ.occurrence_key) == 64  # SHA-256


def test_weekly_multiple_weekdays():
    """Verify weekly recurrence with Monday and Friday (MO, FR)."""
    occurrences = RecurrenceService.expand_recurrence(
        routine_id=ROUTINE_ID,
        rule_version=RULE_VERSION,
        rrule_string="FREQ=WEEKLY;BYDAY=MO,FR",
        dtstart_local="2026-10-19T09:00:00",  # Oct 19, 2026 is Monday
        timezone=DEFAULT_TZ,
        max_occurrences=4,
    )

    assert len(occurrences) == 4
    assert occurrences[0].local_time.startswith("2026-10-19T09:00:00")  # Mon
    assert occurrences[1].local_time.startswith("2026-10-23T09:00:00")  # Fri
    assert occurrences[2].local_time.startswith("2026-10-26T09:00:00")  # Mon
    assert occurrences[3].local_time.startswith("2026-10-30T09:00:00")  # Fri


def test_monthly_weekday_position():
    """Verify 'Every second Tuesday' (FREQ=MONTHLY;BYDAY=2TU)."""
    occurrences = RecurrenceService.expand_recurrence(
        routine_id=ROUTINE_ID,
        rule_version=RULE_VERSION,
        rrule_string="FREQ=MONTHLY;BYDAY=2TU",
        dtstart_local="2026-10-01T10:00:00",
        timezone=DEFAULT_TZ,
        max_occurrences=3,
    )

    assert len(occurrences) == 3
    # Oct 2026: 2nd Tuesday is Oct 13
    assert occurrences[0].local_time.startswith("2026-10-13T10:00:00")
    # Nov 2026: 2nd Tuesday is Nov 10
    assert occurrences[1].local_time.startswith("2026-11-10T10:00:00")
    # Dec 2026: 2nd Tuesday is Dec 08
    assert occurrences[2].local_time.startswith("2026-12-08T10:00:00")


def test_count_constraint():
    """Verify COUNT parameter limits expansion."""
    occurrences = RecurrenceService.expand_recurrence(
        routine_id=ROUTINE_ID,
        rule_version=RULE_VERSION,
        rrule_string="FREQ=DAILY;COUNT=3",
        dtstart_local="2026-10-19T07:00:00",
        timezone=DEFAULT_TZ,
        max_occurrences=100,
    )
    assert len(occurrences) == 3


def test_until_constraint():
    """Verify UNTIL parameter limits expansion."""
    occurrences = RecurrenceService.expand_recurrence(
        routine_id=ROUTINE_ID,
        rule_version=RULE_VERSION,
        rrule_string="FREQ=DAILY;UNTIL=20261021T235959",
        dtstart_local="2026-10-19T07:00:00",
        timezone=DEFAULT_TZ,
        max_occurrences=100,
    )
    assert len(occurrences) == 3
    assert occurrences[-1].local_time.startswith("2026-10-21")


def test_exdate_exclusion():
    """Verify that EXDATE skips specific dates from the occurrence stream."""
    occurrences = RecurrenceService.expand_recurrence(
        routine_id=ROUTINE_ID,
        rule_version=RULE_VERSION,
        rrule_string="FREQ=DAILY;COUNT=5",
        dtstart_local="2026-10-19T08:00:00",
        timezone=DEFAULT_TZ,
        max_occurrences=10,
        exdates=["2026-10-20T08:00:00"],  # Exclude second occurrence
    )

    # Oct 19, 21, 22, 23 (4 occurrences remaining out of 5 planned)
    assert len(occurrences) == 4
    dates = [occ.local_time[:10] for occ in occurrences]
    assert "2026-10-20" not in dates
    assert "2026-10-19" in dates
    assert "2026-10-21" in dates


def test_invalid_rrule_rejection():
    """Verify invalid RFC 5545 strings are rejected with ValidationError."""
    with pytest.raises(ValidationError):
        RecurrenceService.expand_recurrence(
            routine_id=ROUTINE_ID,
            rule_version=RULE_VERSION,
            rrule_string="FREQ=INVALID_FREQUENCY",
            dtstart_local="2026-10-19T08:00:00",
            timezone=DEFAULT_TZ,
        )
