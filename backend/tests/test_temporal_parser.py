"""Tests for TemporalParser: relative, exact, combined, ambiguity, and edge cases."""

from datetime import date, datetime, time
import pytest
from app.temporal.parser import TemporalParser
from app.temporal.schemas import TemporalResolutionStatus
from app.temporal.timezone import UTC

# Reference time: Sunday, Oct 18, 2026, 10:00:00 IST (04:30:00 UTC)
REF_UTC = datetime(2026, 10, 18, 4, 30, 0, tzinfo=UTC)
DEFAULT_TZ = "Asia/Kolkata"


def test_relative_today():
    """Verify 'today' resolves to the reference calendar date."""
    res = TemporalParser.resolve("today", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.PARTIALLY_RESOLVED
    assert res.parsed_date == date(2026, 10, 18)
    assert "2026-10-18" in res.resolved_local


def test_relative_yesterday():
    """Verify 'yesterday' resolves to reference date minus 1 day."""
    res = TemporalParser.resolve("yesterday", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.PARTIALLY_RESOLVED
    assert res.parsed_date == date(2026, 10, 17)


def test_relative_tomorrow():
    """Verify 'tomorrow' resolves to reference date plus 1 day."""
    res = TemporalParser.resolve("tomorrow", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.PARTIALLY_RESOLVED
    assert res.parsed_date == date(2026, 10, 19)


def test_relative_tonight():
    """Verify 'tonight' resolves to reference date anchored at 21:00:00."""
    res = TemporalParser.resolve("tonight", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.RESOLVED
    assert res.parsed_date == date(2026, 10, 18)
    assert res.parsed_time == time(21, 0, 0)
    assert "2026-10-18T21:00:00+05:30" in res.resolved_local
    assert res.resolved_utc == "2026-10-18T15:30:00Z"


def test_relative_day_parts():
    """Verify 'this morning', 'this afternoon', 'this evening'."""
    morn = TemporalParser.resolve("this morning", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert morn.parsed_time == time(9, 0, 0)

    aft = TemporalParser.resolve("this afternoon", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert aft.parsed_time == time(14, 0, 0)

    eve = TemporalParser.resolve("this evening", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert eve.parsed_time == time(18, 0, 0)


def test_next_weekday_semantics():
    """Verify 'next Monday' resolves correctly relative to Sunday Oct 18, 2026."""
    # On Sunday Oct 18, 2026: next Monday is Oct 19, 2026 (1 day ahead)
    res = TemporalParser.resolve("next Monday", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.parsed_date == date(2026, 10, 19)

    # Reference on Monday Oct 19, 2026:
    ref_monday = datetime(2026, 10, 19, 4, 30, 0, tzinfo=UTC)
    res_mon = TemporalParser.resolve("next Monday", reference_time_utc=ref_monday, timezone=DEFAULT_TZ)
    # Next Monday from a Monday must be 7 days ahead (Oct 26)
    assert res_mon.parsed_date == date(2026, 10, 26)


def test_previous_weekday():
    """Verify 'last Friday' resolves to the preceding Friday."""
    # Ref Sunday Oct 18: preceding Friday was Oct 16
    res = TemporalParser.resolve("last Friday", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.parsed_date == date(2026, 10, 16)


def test_relative_durations():
    """Verify relative durations: 'in two hours', 'in 3 days', 'in 30 minutes'."""
    res_2h = TemporalParser.resolve("in two hours", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_2h.status == TemporalResolutionStatus.RESOLVED
    assert res_2h.resolved_utc == "2026-10-18T06:30:00Z"

    res_3d = TemporalParser.resolve("in 3 days", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_3d.parsed_date == date(2026, 10, 21)

    res_30m = TemporalParser.resolve("in 30 minutes", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_30m.resolved_utc == "2026-10-18T05:00:00Z"


def test_exact_time_parsing():
    """Verify exact 12-hour and 24-hour time parsing."""
    # 12:00 AM as 00:00
    res_12am = TemporalParser.resolve("12:00 AM", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_12am.parsed_time == time(0, 0, 0)

    # 12:00 PM as 12:00
    res_12pm = TemporalParser.resolve("12:00 PM", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_12pm.parsed_time == time(12, 0, 0)

    # 2 PM as 14:00
    res_2pm = TemporalParser.resolve("2 PM", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_2pm.parsed_time == time(14, 0, 0)

    # 14:30 as 14:30
    res_1430 = TemporalParser.resolve("14:30", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_1430.parsed_time == time(14, 30, 0)


def test_combined_datetime_tomorrow_at_2pm():
    """Verify 'tomorrow at 2 PM' resolves to tomorrow at 14:00 in Asia/Kolkata and converts to UTC."""
    res = TemporalParser.resolve("tomorrow at 2 PM", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.RESOLVED
    assert res.parsed_date == date(2026, 10, 19)
    assert res.parsed_time == time(14, 0, 0)
    assert "2026-10-19T14:00:00+05:30" in res.resolved_local
    # 14:00 IST = 08:30 UTC
    assert res.resolved_utc == "2026-10-19T08:30:00Z"
    assert res.confidence == 1.0


def test_combined_datetime_next_monday_at_2pm():
    """Verify 'next Monday at 2 PM'."""
    res = TemporalParser.resolve("next Monday at 2 PM", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.RESOLVED
    assert res.parsed_date == date(2026, 10, 19)
    assert res.parsed_time == time(14, 0, 0)


def test_combined_weekday_daypart():
    """Verify 'Friday morning' resolves to upcoming Friday at 09:00."""
    res = TemporalParser.resolve("Friday morning", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.RESOLVED
    assert res.parsed_date == date(2026, 10, 23)
    assert res.parsed_time == time(9, 0, 0)


def test_ambiguous_time_at_2():
    """Verify 'at 2' returns AMBIGUOUS with 2:00 AM and 2:00 PM clarification options."""
    res = TemporalParser.resolve("at 2", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.AMBIGUOUS
    assert res.is_ambiguous is True
    assert res.ambiguity_details is not None
    assert len(res.ambiguity_details.options) == 2

    labels = [opt.label for opt in res.ambiguity_details.options]
    assert "02:00 AM" in labels
    assert "02:00 PM" in labels


def test_ambiguous_weekday_this_friday_on_friday():
    """Verify 'this Friday' on a Friday returns AMBIGUOUS with Today vs Next Friday."""
    # Set reference time to Friday Oct 23, 2026
    ref_friday = datetime(2026, 10, 23, 4, 30, 0, tzinfo=UTC)
    res = TemporalParser.resolve("this Friday", reference_time_utc=ref_friday, timezone=DEFAULT_TZ)

    assert res.status == TemporalResolutionStatus.AMBIGUOUS
    assert res.is_ambiguous is True
    assert res.ambiguity_details is not None
    assert len(res.ambiguity_details.options) == 2
    assert "Today" in res.ambiguity_details.options[0].label
    assert "Next Friday" in res.ambiguity_details.options[1].label


def test_missing_context_after_the_meeting():
    """Verify 'after the meeting' returns MISSING_CONTEXT."""
    res = TemporalParser.resolve("after the meeting", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res.status == TemporalResolutionStatus.MISSING_CONTEXT
    assert res.is_ambiguous is True
    assert res.confidence == 0.0


def test_month_end_resolution():
    """Verify 'month-end' handles 31-day, 30-day, leap year Feb, and non-leap Feb."""
    # October 2026 (31 days)
    res_oct = TemporalParser.resolve("month-end", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_oct.parsed_date == date(2026, 10, 31)

    # Leap year Feb (2024 -> 29 days)
    ref_leap = datetime(2024, 2, 10, 4, 30, 0, tzinfo=UTC)
    res_leap = TemporalParser.resolve("month-end", reference_time_utc=ref_leap, timezone=DEFAULT_TZ)
    assert res_leap.parsed_date == date(2024, 2, 29)

    # Non-leap year Feb (2025 -> 28 days)
    ref_non_leap = datetime(2025, 2, 10, 4, 30, 0, tzinfo=UTC)
    res_non_leap = TemporalParser.resolve("month-end", reference_time_utc=ref_non_leap, timezone=DEFAULT_TZ)
    assert res_non_leap.parsed_date == date(2025, 2, 28)


def test_invalid_date_or_time():
    """Verify invalid expressions return INVALID status."""
    res1 = TemporalParser.resolve("not a valid time at all", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res1.status == TemporalResolutionStatus.INVALID

    res2 = TemporalParser.resolve("tomorrow at 25:99", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res2.status == TemporalResolutionStatus.INVALID


def test_exact_date_formats():
    """Verify various exact date formats."""
    # ISO
    res_iso = TemporalParser.resolve("2026-10-18", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_iso.parsed_date == date(2026, 10, 18)

    # DD-MM-YYYY
    res_dmy = TemporalParser.resolve("18-10-2026", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_dmy.parsed_date == date(2026, 10, 18)

    # Named month
    res_named = TemporalParser.resolve("October 18, 2026", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_named.parsed_date == date(2026, 10, 18)


def test_february_29_leap_vs_non_leap():
    """Verify Feb 29 on leap year succeeds, and invalid non-leap year Feb 29 is rejected as INVALID."""
    res_leap = TemporalParser.resolve("2024-02-29", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_leap.status == TemporalResolutionStatus.PARTIALLY_RESOLVED
    assert res_leap.parsed_date == date(2024, 2, 29)

    res_non_leap = TemporalParser.resolve("2025-02-29", reference_time_utc=REF_UTC, timezone=DEFAULT_TZ)
    assert res_non_leap.status == TemporalResolutionStatus.INVALID
