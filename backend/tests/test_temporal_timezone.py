"""Tests for TimezoneService: validation, UTC/local conversion, Asia/Kolkata default, and DST."""

from datetime import datetime
import pytest
import zoneinfo
from app.core.exceptions import ValidationError
from app.temporal.timezone import TimezoneService, UTC


def test_default_asia_kolkata_timezone():
    """Verify that the default configured timezone resolves to Asia/Kolkata."""
    effective_tz = TimezoneService.get_effective_timezone(None)
    assert effective_tz == "Asia/Kolkata"
    zone = TimezoneService.get_zone_info(None)
    assert zone.key == "Asia/Kolkata"


def test_valid_iana_timezone():
    """Verify that recognized IANA timezones validate correctly."""
    assert TimezoneService.is_valid_iana_timezone("Asia/Kolkata") is True
    assert TimezoneService.is_valid_iana_timezone("America/New_York") is True
    assert TimezoneService.is_valid_iana_timezone("Europe/London") is True
    assert TimezoneService.is_valid_iana_timezone("UTC") is True


def test_invalid_timezone_rejection():
    """Verify that invalid timezone strings are rejected."""
    assert TimezoneService.is_valid_iana_timezone("Invalid/Nowhere") is False
    assert TimezoneService.is_valid_iana_timezone("") is False
    assert TimezoneService.is_valid_iana_timezone("Moon/Base") is False

    with pytest.raises(ValidationError) as exc:
        TimezoneService.validate_or_raise("Invalid/Nowhere")
    assert "Invalid IANA timezone" in str(exc.value)


def test_utc_to_local_conversion_asia_kolkata():
    """Verify converting UTC datetime to Asia/Kolkata (+05:30)."""
    # 2026-10-18 08:30:00 UTC -> 2026-10-18 14:00:00 IST
    utc_dt = datetime(2026, 10, 18, 8, 30, 0, tzinfo=UTC)
    local_dt = TimezoneService.to_local(utc_dt, "Asia/Kolkata")

    assert local_dt.year == 2026
    assert local_dt.month == 10
    assert local_dt.day == 18
    assert local_dt.hour == 14
    assert local_dt.minute == 0
    assert TimezoneService.get_utc_offset_str("Asia/Kolkata", utc_dt) == "+05:30"


def test_local_to_utc_conversion():
    """Verify converting local datetime to UTC."""
    # 2026-10-19 14:00:00 IST -> 2026-10-19 08:30:00 UTC
    local_naive = datetime(2026, 10, 19, 14, 0, 0)
    utc_dt = TimezoneService.to_utc(local_naive, "Asia/Kolkata")

    assert utc_dt.tzinfo == UTC
    assert utc_dt.year == 2026
    assert utc_dt.month == 10
    assert utc_dt.day == 19
    assert utc_dt.hour == 8
    assert utc_dt.minute == 30
    assert TimezoneService.format_utc_instant(utc_dt) == "2026-10-19T08:30:00Z"


def test_dst_aware_behavior():
    """Verify DST detection and offset transition for DST-observing zones."""
    tz = "America/New_York"
    # Summer (EDT, UTC-4)
    summer_dt = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    assert TimezoneService.is_dst(tz, summer_dt) is True
    assert TimezoneService.get_utc_offset_str(tz, summer_dt) == "-04:00"

    # Winter (EST, UTC-5)
    winter_dt = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert TimezoneService.is_dst(tz, winter_dt) is False
    assert TimezoneService.get_utc_offset_str(tz, winter_dt) == "-05:00"

    # Asia/Kolkata does not observe DST
    assert TimezoneService.is_dst("Asia/Kolkata", summer_dt) is False
    assert TimezoneService.is_dst("Asia/Kolkata", winter_dt) is False


def test_preserve_utc_on_timezone_change():
    """Verify that shifting user timezone preserves the absolute UTC instant."""
    from app.temporal.resolver import TemporalService

    original_utc = datetime(2026, 10, 18, 8, 30, 0, tzinfo=UTC)
    # User was in Asia/Kolkata (14:00 local)
    kolkata_local = TimezoneService.format_local_iso(original_utc, "Asia/Kolkata")
    assert "14:00:00+05:30" in kolkata_local

    # User changes timezone to America/New_York (-04:00 EDT)
    preserved_utc, new_local = TemporalService.preserve_utc_on_timezone_change(
        original_utc, "America/New_York"
    )
    assert preserved_utc == original_utc
    assert "04:30:00-04:00" in new_local
