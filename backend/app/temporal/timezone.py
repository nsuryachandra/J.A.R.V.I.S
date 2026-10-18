"""Deterministic, IANA-compliant timezone service and datetime conversion."""

from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Optional
import zoneinfo
from app.core.config import get_settings
from app.core.exceptions import ValidationError

UTC = zoneinfo.ZoneInfo("UTC")


class TimezoneService:
    """Service handling IANA timezone validation, local<->UTC conversions, and offsets."""

    @staticmethod
    def is_valid_iana_timezone(tz_name: str) -> bool:
        """Check whether a timezone string is a recognized IANA timezone identifier."""
        if not tz_name or not isinstance(tz_name, str):
            return False
        try:
            zoneinfo.ZoneInfo(tz_name)
            return True
        except Exception:
            return False

    @classmethod
    def validate_or_raise(cls, tz_name: str) -> zoneinfo.ZoneInfo:
        """Validate an IANA timezone string and return the ZoneInfo object, or raise ValidationError."""
        if not tz_name or not isinstance(tz_name, str):
            raise ValidationError(f"Invalid timezone: '{tz_name}' is empty or not a string")
        try:
            return zoneinfo.ZoneInfo(tz_name)
        except Exception as exc:
            raise ValidationError(f"Invalid IANA timezone '{tz_name}'") from exc

    @classmethod
    def get_effective_timezone(cls, tz_name: Optional[str] = None) -> str:
        """Resolve the effective timezone name using configured default policy."""
        if tz_name and cls.is_valid_iana_timezone(tz_name):
            return tz_name
        settings = get_settings()
        return settings.timezone

    @classmethod
    def get_zone_info(cls, tz_name: Optional[str] = None) -> zoneinfo.ZoneInfo:
        """Return the ZoneInfo object for the given timezone or system default."""
        effective_name = cls.get_effective_timezone(tz_name)
        return zoneinfo.ZoneInfo(effective_name)

    @classmethod
    def to_utc(cls, dt: datetime, tz_name: Optional[str] = None) -> datetime:
        """Normalize any datetime (local naive or aware) into an aware UTC datetime."""
        if dt.tzinfo is None:
            # Naive datetime: localize to the specified timezone
            zone = cls.get_zone_info(tz_name)
            localized = dt.replace(tzinfo=zone)
            return localized.astimezone(UTC)
        # Already aware: convert directly to UTC
        return dt.astimezone(UTC)

    @classmethod
    def to_local(cls, dt: datetime, tz_name: Optional[str] = None) -> datetime:
        """Convert a datetime (UTC or aware) into an aware datetime in the target timezone."""
        zone = cls.get_zone_info(tz_name)
        if dt.tzinfo is None:
            # Naive datetime: assume it represents UTC
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(zone)

    @classmethod
    def format_utc_instant(cls, dt: datetime) -> str:
        """Format an aware UTC datetime as standard ISO 8601 with Z suffix."""
        utc_dt = cls.to_utc(dt)
        return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    @classmethod
    def format_local_iso(cls, dt: datetime, tz_name: Optional[str] = None) -> str:
        """Format a datetime in the target timezone with explicit offset."""
        local_dt = cls.to_local(dt, tz_name)
        return local_dt.isoformat()

    @classmethod
    def get_utc_offset_str(cls, tz_name: str, at_dt: Optional[datetime] = None) -> str:
        """Calculate the UTC offset string (+HH:MM or -HH:MM) for a timezone at a specific datetime."""
        zone = cls.validate_or_raise(tz_name)
        target = at_dt or datetime.now(dt_timezone.utc)
        if target.tzinfo is None:
            target = target.replace(tzinfo=dt_timezone.utc)
        localized = target.astimezone(zone)
        offset = localized.utcoffset()
        if offset is None:
            return "+00:00"
        total_seconds = int(offset.total_seconds())
        sign = "+" if total_seconds >= 0 else "-"
        abs_seconds = abs(total_seconds)
        hours = abs_seconds // 3600
        minutes = (abs_seconds % 3600) // 60
        return f"{sign}{hours:02d}:{minutes:02d}"

    @classmethod
    def is_dst(cls, tz_name: str, at_dt: Optional[datetime] = None) -> bool:
        """Determine whether daylight saving time (DST) is active for a timezone at a given instant."""
        zone = cls.validate_or_raise(tz_name)
        target = at_dt or datetime.now(dt_timezone.utc)
        if target.tzinfo is None:
            target = target.replace(tzinfo=dt_timezone.utc)
        localized = target.astimezone(zone)
        dst = localized.dst()
        return bool(dst and dst != timedelta(0))
