"""RFC 5545 recurrence rule parsing, expansion, and occurrence generator."""

from datetime import datetime, date, time
from typing import List, Optional
from uuid import UUID
from dateutil.rrule import rrulestr, rruleset
from app.core.exceptions import ValidationError
from app.temporal.identity import OccurrenceIdentityGenerator
from app.temporal.schemas import RecurrenceOccurrence
from app.temporal.timezone import TimezoneService, UTC

MAX_OCCURRENCES_LIMIT = 365


class RecurrenceService:
    """Service to parse, validate, and expand RFC 5545 recurrence rules deterministically."""

    @classmethod
    def parse_iso_or_datetime(cls, val: str | datetime | date) -> datetime:
        """Parse an ISO date or datetime string into a naive datetime for local calendar evaluation."""
        if isinstance(val, datetime):
            return val.replace(tzinfo=None)
        if isinstance(val, date):
            return datetime.combine(val, time.min)
        if isinstance(val, str):
            clean = val.strip().replace("Z", "")
            # Remove trailing offset if present (e.g. +05:30)
            if "+" in clean:
                clean = clean.split("+")[0]
            elif "-" in clean and clean.count("-") > 2:
                # format with negative offset like 2026-10-18T14:00:00-04:00
                parts = clean.rsplit("-", 1)
                clean = parts[0]
            try:
                return datetime.fromisoformat(clean)
            except Exception as exc:
                raise ValidationError(f"Invalid date/datetime format '{val}': {exc}") from exc
        raise ValidationError(f"Unsupported datetime type: {type(val)}")

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
        """
        Expand an RFC 5545 recurrence rule within local calendar time,
        convert each occurrence to UTC, apply window and exdate constraints,
        and assign deterministic occurrence identities.
        """
        tz = TimezoneService.get_effective_timezone(timezone)
        TimezoneService.validate_or_raise(tz)

        # Parse local start datetime
        dtstart = cls.parse_iso_or_datetime(dtstart_local)

        # Cap max occurrences to avoid resource exhaustion
        effective_max = max(1, min(max_occurrences, MAX_OCCURRENCES_LIMIT))

        # Build rruleset
        try:
            # rrulestr requires uppercase or standardized string
            rule_str = rrule_string.strip()
            if not rule_str.upper().startswith("RRULE:"):
                # If just 'FREQ=...', we can parse directly
                parsed_rrule = rrulestr(rule_str, dtstart=dtstart)
            else:
                parsed_rrule = rrulestr(rule_str, dtstart=dtstart)
        except Exception as exc:
            raise ValidationError(f"Invalid RFC 5545 recurrence rule '{rrule_string}': {exc}") from exc

        rule_set = rruleset()
        rule_set.rrule(parsed_rrule)

        # Add exdates if any
        if exdates:
            for ex in exdates:
                try:
                    ex_dt = cls.parse_iso_or_datetime(ex)
                    rule_set.exdate(ex_dt)
                except Exception as exc:
                    raise ValidationError(f"Invalid EXDATE format '{ex}': {exc}") from exc

        # Expand occurrences in local calendar time
        occurrences: List[RecurrenceOccurrence] = []
        zone = TimezoneService.get_zone_info(tz)

        # We iterate over generated local datetimes
        seq_idx = 0
        for local_dt in rule_set:
            # Localize to target timezone
            aware_local = local_dt.replace(tzinfo=zone)
            aware_utc = aware_local.astimezone(UTC)

            # Apply window filtering if provided
            if window_start_utc:
                win_start = TimezoneService.to_utc(window_start_utc)
                if aware_utc < win_start:
                    continue
            if window_end_utc:
                win_end = TimezoneService.to_utc(window_end_utc)
                if aware_utc > win_end:
                    break

            seq_idx += 1
            local_iso = aware_local.isoformat()
            utc_iso = aware_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

            # Deterministic occurrence key
            key = OccurrenceIdentityGenerator.generate_key(
                routine_id=routine_id,
                rule_version=rule_version,
                local_date_time=local_iso,
                timezone=tz,
                sequence_index=seq_idx,
            )

            occurrences.append(
                RecurrenceOccurrence(
                    occurrence_key=key,
                    sequence_index=seq_idx,
                    local_time=local_iso,
                    utc_instant=utc_iso,
                    is_exception=False,
                )
            )

            if len(occurrences) >= effective_max:
                break

        return occurrences
