"""Deterministic relative, exact, and combined temporal expression parser."""

import calendar
from datetime import date, datetime, time, timedelta
import re
from typing import Any, List, Optional, Tuple
from app.temporal.schemas import (
    ClarificationOption,
    TemporalAmbiguity,
    TemporalProvenance,
    TemporalResolution,
    TemporalResolutionStatus,
)
from app.temporal.timezone import TimezoneService, UTC

PARSER_VERSION = "1.0.0"

WORD_NUMBERS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTH_NAMES = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


class TemporalParser:
    """Deterministic parser converting natural-language temporal expressions into normalized timestamps."""

    @classmethod
    def parse_time_component(cls, text: str) -> Tuple[Optional[time], bool, Optional[Tuple[time, time]]]:
        """
        Parse time string.
        Returns:
            (resolved_time, is_ambiguous, ambiguous_pair)
        """
        clean = text.strip().lower()
        if clean.startswith("at "):
            clean = clean[3:].strip()

        # Check for anchors like 'noon', 'midnight'
        if clean == "noon":
            return time(12, 0), False, None
        if clean == "midnight":
            return time(0, 0), False, None

        # Check for explicit AM/PM: e.g. "12:00 am", "12:00 pm", "2 pm", "9 am", "2:30 pm"
        m_ampm = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", clean)
        if m_ampm:
            hour = int(m_ampm.group(1))
            minute = int(m_ampm.group(2) or 0)
            ampm = m_ampm.group(3)

            if hour < 1 or hour > 12 or minute < 0 or minute > 59:
                return None, False, None

            if ampm == "am":
                hour = 0 if hour == 12 else hour
            else:  # pm
                hour = 12 if hour == 12 else hour + 12

            return time(hour, minute), False, None

        # Check for 24-hour time: e.g. "14:30", "09:00", "00:00", "23:59"
        m_24 = re.match(r"^(\d{1,2}):(\d{2})$", clean)
        if m_24:
            hour = int(m_24.group(1))
            minute = int(m_24.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return time(hour, minute), False, None
            return None, False, None

        # Bare single hour without AM/PM: e.g. "2", "at 2", "5"
        m_bare = re.match(r"^(\d{1,2})(?::(\d{2}))?$", clean)
        if m_bare:
            hour = int(m_bare.group(1))
            minute = int(m_bare.group(2) or 0)
            if 1 <= hour <= 12 and 0 <= minute <= 59:
                # Ambiguous: could be AM or PM
                am_hour = 0 if hour == 12 else hour
                pm_hour = 12 if hour == 12 else hour + 12
                t_am = time(am_hour, minute)
                t_pm = time(pm_hour, minute)
                return None, True, (t_am, t_pm)
            elif 13 <= hour <= 23 and 0 <= minute <= 59:
                # Clearly 24-hour hour
                return time(hour, minute), False, None

        return None, False, None

    @classmethod
    def parse_relative_date(
        cls,
        text: str,
        ref_local: datetime,
    ) -> Tuple[Optional[date], bool, Optional[Tuple[date, date]], Optional[time]]:
        """
        Parse relative date keywords.
        Returns:
            (resolved_date, is_ambiguous, ambiguous_pair, anchored_time)
        """
        clean = text.strip().lower()
        ref_date = ref_local.date()

        # Day anchors
        if clean == "today":
            return ref_date, False, None, None
        if clean == "yesterday":
            return ref_date - timedelta(days=1), False, None, None
        if clean == "tomorrow":
            return ref_date + timedelta(days=1), False, None, None

        # Day-part anchors (today)
        if clean == "tonight":
            return ref_date, False, None, time(21, 0, 0)
        if clean == "this morning":
            return ref_date, False, None, time(9, 0, 0)
        if clean == "this afternoon":
            return ref_date, False, None, time(14, 0, 0)
        if clean == "this evening":
            return ref_date, False, None, time(18, 0, 0)

        # Month-end
        if clean in ("month-end", "month end", "end of the month", "end of month"):
            last_day = calendar.monthrange(ref_date.year, ref_date.month)[1]
            return date(ref_date.year, ref_date.month, last_day), False, None, None

        # Next / Last month
        if clean in ("next month",):
            year = ref_date.year + 1 if ref_date.month == 12 else ref_date.year
            month = 1 if ref_date.month == 12 else ref_date.month + 1
            return date(year, month, 1), False, None, None
        if clean in ("last month",):
            year = ref_date.year - 1 if ref_date.month == 1 else ref_date.year
            month = 12 if ref_date.month == 1 else ref_date.month - 1
            return date(year, month, 1), False, None, None

        # Weekday phrases: "this Friday", "next Monday", "last Friday"
        for w_name, w_idx in WEEKDAY_NAMES.items():
            # "this <weekday>"
            if clean == f"this {w_name}":
                cur_w = ref_date.weekday()
                if cur_w == w_idx:
                    # Current day matches the weekday!
                    # Ambiguity policy: Ambiguous between today and next week's occurrence
                    d1 = ref_date
                    d2 = ref_date + timedelta(days=7)
                    return None, True, (d1, d2), None
                elif cur_w < w_idx:
                    # Upcoming in current week
                    return ref_date + timedelta(days=(w_idx - cur_w)), False, None, None
                else:
                    # Already passed in current week, refers to next week
                    return ref_date + timedelta(days=(7 - (cur_w - w_idx))), False, None, None

            # "next <weekday>"
            if clean == f"next {w_name}":
                cur_w = ref_date.weekday()
                # Next occurrence in the following week
                days_ahead = (w_idx - cur_w) % 7
                if days_ahead == 0:
                    days_ahead = 7
                elif cur_w + days_ahead < 7 and cur_w < w_idx:
                    # If it's upcoming this week, "next <weekday>" strictly means next week's occurrence
                    days_ahead += 7
                return ref_date + timedelta(days=days_ahead), False, None, None

            # "last <weekday>"
            if clean == f"last {w_name}":
                cur_w = ref_date.weekday()
                days_behind = (cur_w - w_idx) % 7
                if days_behind == 0:
                    days_behind = 7
                return ref_date - timedelta(days=days_behind), False, None, None

            # Combined weekday and day-part: e.g. "Friday morning", "Friday afternoon", "Friday evening", "Friday night"
            for part, p_time in [
                ("morning", time(9, 0)),
                ("afternoon", time(14, 0)),
                ("evening", time(18, 0)),
                ("night", time(21, 0)),
            ]:
                if clean == f"{w_name} {part}":
                    cur_w = ref_date.weekday()
                    days_ahead = (w_idx - cur_w) % 7
                    if days_ahead == 0 and ref_local.time() > p_time:
                        days_ahead = 7
                    target_date = ref_date + timedelta(days=days_ahead)
                    return target_date, False, None, p_time

        return None, False, None, None

    @classmethod
    def parse_relative_duration(cls, text: str, ref_local: datetime) -> Optional[datetime]:
        """Parse durations like 'in two hours', 'in 3 days', 'in 30 minutes', 'in 2 weeks'."""
        clean = text.strip().lower()
        m = re.match(r"^in\s+(\w+)\s+(second|minute|hour|day|week|month)s?$", clean)
        if not m:
            return None

        val_str = m.group(1)
        unit = m.group(2)

        count: int
        if val_str in WORD_NUMBERS:
            count = WORD_NUMBERS[val_str]
        elif val_str.isdigit():
            count = int(val_str)
        else:
            return None

        if unit == "second":
            return ref_local + timedelta(seconds=count)
        if unit == "minute":
            return ref_local + timedelta(minutes=count)
        if unit == "hour":
            return ref_local + timedelta(hours=count)
        if unit == "day":
            return ref_local + timedelta(days=count)
        if unit == "week":
            return ref_local + timedelta(weeks=count)
        if unit == "month":
            # Approximate 30-day month increment safely
            year = ref_local.year + ((ref_local.month + count - 1) // 12)
            month = ((ref_local.month + count - 1) % 12) + 1
            day = min(ref_local.day, calendar.monthrange(year, month)[1])
            return ref_local.replace(year=year, month=month, day=day)

        return None

    @classmethod
    def parse_exact_date(cls, text: str) -> Optional[date]:
        """Parse exact calendar dates like '2026-10-18', '18-10-2026', 'October 18, 2026', '18 Oct 2026'."""
        clean = text.strip()

        # ISO format: YYYY-MM-DD
        if re.match(r"^\d{4}-\d{2}-\d{2}$", clean):
            try:
                return date.fromisoformat(clean)
            except ValueError:
                return None

        # DD-MM-YYYY or DD/MM/YYYY
        m_dmy = re.match(r"^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$", clean)
        if m_dmy:
            day = int(m_dmy.group(1))
            month = int(m_dmy.group(2))
            year = int(m_dmy.group(3))
            try:
                return date(year, month, day)
            except ValueError:
                return None

        # Named month: e.g. "October 18, 2026" or "18 Oct 2026"
        m_named1 = re.match(r"^([a-zA-Z]+)\s+(\d{1,2}),?\s*(\d{4})?$", clean)
        if m_named1:
            m_str = m_named1.group(1).lower()
            if m_str in MONTH_NAMES:
                month = MONTH_NAMES[m_str]
                day = int(m_named1.group(2))
                year = int(m_named1.group(3) or date.today().year)
                try:
                    return date(year, month, day)
                except ValueError:
                    return None

        m_named2 = re.match(r"^(\d{1,2})\s+([a-zA-Z]+),?\s*(\d{4})?$", clean)
        if m_named2:
            m_str = m_named2.group(2).lower()
            if m_str in MONTH_NAMES:
                month = MONTH_NAMES[m_str]
                day = int(m_named2.group(1))
                year = int(m_named2.group(3) or date.today().year)
                try:
                    return date(year, month, day)
                except ValueError:
                    return None

        return None

    @classmethod
    def resolve(
        cls,
        text: str,
        reference_time_utc: Optional[datetime] = None,
        timezone: Optional[str] = None,
        user_id: Optional[Any] = None,
    ) -> TemporalResolution:
        """
        Main deterministic resolution entrypoint.
        Processes relative dates, exact dates, times, ambiguity, and conversions.
        """
        tz = TimezoneService.get_effective_timezone(timezone)
        TimezoneService.validate_or_raise(tz)

        # Establish reference local datetime
        ref_utc = reference_time_utc or datetime.now(UTC)
        if ref_utc.tzinfo is None:
            ref_utc = ref_utc.replace(tzinfo=UTC)
        ref_local = TimezoneService.to_local(ref_utc, tz)
        ref_date = ref_local.date()

        raw = text.strip()

        # Check for context-dependent ungrounded references
        if any(unsupported in raw.lower() for unsupported in ["after the meeting", "after lunch", "after my call"]):
            return TemporalResolution(
                original_text=raw,
                status=TemporalResolutionStatus.MISSING_CONTEXT,
                confidence=0.0,
                timezone=tz,
                is_ambiguous=True,
                ambiguity_details=TemporalAmbiguity(
                    reason="Reference event has no known timestamp context",
                    clarification_prompt=f"At what time does '{raw}' occur?",
                    options=[],
                ),
                provenance=TemporalProvenance(
                    original_text=raw,
                    timezone_used=tz,
                    reference_time_utc=ref_utc,
                    parser_version=PARSER_VERSION,
                    resolution_status=TemporalResolutionStatus.MISSING_CONTEXT,
                    resolution_method="event_reference_missing_context",
                    confidence=0.0,
                ),
            )

        # Check relative duration (e.g. 'in two hours', 'in 3 days')
        dt_duration = cls.parse_relative_duration(raw, ref_local)
        if dt_duration is not None:
            aware_local = dt_duration
            aware_utc = TimezoneService.to_utc(aware_local, tz)
            return TemporalResolution(
                original_text=raw,
                status=TemporalResolutionStatus.RESOLVED,
                confidence=1.0,
                timezone=tz,
                resolved_local=TimezoneService.format_local_iso(aware_local, tz),
                resolved_utc=TimezoneService.format_utc_instant(aware_utc),
                is_ambiguous=False,
                parsed_date=aware_local.date(),
                parsed_time=aware_local.time(),
                provenance=TemporalProvenance(
                    original_text=raw,
                    timezone_used=tz,
                    reference_time_utc=ref_utc,
                    parser_version=PARSER_VERSION,
                    resolution_status=TemporalResolutionStatus.RESOLVED,
                    resolution_method="relative_duration",
                    confidence=1.0,
                ),
            )

        # Check combined expression: "<date_part> at <time_part>"
        m_at = re.match(r"^(.*?)\s+at\s+(.*?)$", raw, re.IGNORECASE)
        date_str = raw
        time_str: Optional[str] = None
        if m_at:
            date_str = m_at.group(1).strip()
            time_str = m_at.group(2).strip()

        # Parse date part
        parsed_date: Optional[date] = None
        date_is_ambiguous = False
        date_ambiguous_pair: Optional[Tuple[date, date]] = None
        anchored_time: Optional[time] = None

        # Try relative date
        r_date, r_ambig, r_pair, r_anchor = cls.parse_relative_date(date_str, ref_local)
        if r_date or r_ambig or r_anchor:
            parsed_date = r_date
            date_is_ambiguous = r_ambig
            date_ambiguous_pair = r_pair
            anchored_time = r_anchor
        else:
            # Try exact date
            e_date = cls.parse_exact_date(date_str)
            if e_date:
                parsed_date = e_date

        # If date is ambiguous (e.g. "this Friday" on Friday)
        if date_is_ambiguous and date_ambiguous_pair:
            d1, d2 = date_ambiguous_pair
            opt1_dt = datetime.combine(d1, anchored_time or time(9, 0)).replace(tzinfo=TimezoneService.get_zone_info(tz))
            opt2_dt = datetime.combine(d2, anchored_time or time(9, 0)).replace(tzinfo=TimezoneService.get_zone_info(tz))
            opt1_utc = TimezoneService.to_utc(opt1_dt)
            opt2_utc = TimezoneService.to_utc(opt2_dt)

            options = [
                ClarificationOption(
                    option_id="opt_1",
                    label=f"Today ({d1.strftime('%A, %b %d, %Y')})",
                    resolved_local=TimezoneService.format_local_iso(opt1_dt, tz),
                    resolved_utc=TimezoneService.format_utc_instant(opt1_utc),
                ),
                ClarificationOption(
                    option_id="opt_2",
                    label=f"Next {d2.strftime('%A')} ({d2.strftime('%A, %b %d, %Y')})",
                    resolved_local=TimezoneService.format_local_iso(opt2_dt, tz),
                    resolved_utc=TimezoneService.format_utc_instant(opt2_utc),
                ),
            ]
            return TemporalResolution(
                original_text=raw,
                status=TemporalResolutionStatus.AMBIGUOUS,
                confidence=0.5,
                timezone=tz,
                is_ambiguous=True,
                ambiguity_details=TemporalAmbiguity(
                    reason=f"'{date_str}' falls on the current weekday and could mean today or next week",
                    clarification_prompt=f"Today is {d1.strftime('%A')}. Did you mean today ({d1.isoformat()}) or next {d2.strftime('%A')} ({d2.isoformat()})?",
                    options=options,
                ),
                provenance=TemporalProvenance(
                    original_text=raw,
                    timezone_used=tz,
                    reference_time_utc=ref_utc,
                    parser_version=PARSER_VERSION,
                    resolution_status=TemporalResolutionStatus.AMBIGUOUS,
                    resolution_method="relative_weekday_ambiguity",
                    confidence=0.5,
                ),
            )

        # Parse time part if present
        parsed_time: Optional[time] = anchored_time
        time_is_ambiguous = False
        time_ambiguous_pair: Optional[Tuple[time, time]] = None

        if time_str is not None:
            t_val, t_ambig, t_pair = cls.parse_time_component(time_str)
            if t_ambig:
                time_is_ambiguous = True
                time_ambiguous_pair = t_pair
            elif t_val is not None:
                parsed_time = t_val
            else:
                # Time string invalid
                return TemporalResolution(
                    original_text=raw,
                    status=TemporalResolutionStatus.INVALID,
                    confidence=0.0,
                    timezone=tz,
                    is_ambiguous=False,
                    provenance=TemporalProvenance(
                        original_text=raw,
                        timezone_used=tz,
                        reference_time_utc=ref_utc,
                        parser_version=PARSER_VERSION,
                        resolution_status=TemporalResolutionStatus.INVALID,
                        resolution_method="time_component_invalid",
                        confidence=0.0,
                    ),
                )
        elif parsed_date is None:
            # Maybe the whole string is just a time: e.g. "at 2", "2 PM", "14:30"
            t_val, t_ambig, t_pair = cls.parse_time_component(raw)
            if t_ambig:
                time_is_ambiguous = True
                time_ambiguous_pair = t_pair
                parsed_date = ref_date
            elif t_val is not None:
                parsed_time = t_val
                parsed_date = ref_date

        # If time is ambiguous (e.g. "at 2")
        if time_is_ambiguous and time_ambiguous_pair:
            t1, t2 = time_ambiguous_pair
            target_date = parsed_date or ref_date
            opt1_dt = datetime.combine(target_date, t1).replace(tzinfo=TimezoneService.get_zone_info(tz))
            opt2_dt = datetime.combine(target_date, t2).replace(tzinfo=TimezoneService.get_zone_info(tz))
            opt1_utc = TimezoneService.to_utc(opt1_dt)
            opt2_utc = TimezoneService.to_utc(opt2_dt)

            options = [
                ClarificationOption(
                    option_id="opt_am",
                    label=f"{t1.strftime('%I:%M %p')}",
                    resolved_local=TimezoneService.format_local_iso(opt1_dt, tz),
                    resolved_utc=TimezoneService.format_utc_instant(opt1_utc),
                ),
                ClarificationOption(
                    option_id="opt_pm",
                    label=f"{t2.strftime('%I:%M %p')}",
                    resolved_local=TimezoneService.format_local_iso(opt2_dt, tz),
                    resolved_utc=TimezoneService.format_utc_instant(opt2_utc),
                ),
            ]
            return TemporalResolution(
                original_text=raw,
                status=TemporalResolutionStatus.AMBIGUOUS,
                confidence=0.5,
                timezone=tz,
                is_ambiguous=True,
                ambiguity_details=TemporalAmbiguity(
                    reason="Hour provided without AM or PM designation",
                    clarification_prompt=f"Did you mean {t1.strftime('%I:%M %p')} or {t2.strftime('%I:%M %p')}?",
                    options=options,
                ),
                provenance=TemporalProvenance(
                    original_text=raw,
                    timezone_used=tz,
                    reference_time_utc=ref_utc,
                    parser_version=PARSER_VERSION,
                    resolution_status=TemporalResolutionStatus.AMBIGUOUS,
                    resolution_method="time_am_pm_ambiguity",
                    confidence=0.5,
                ),
            )

        # If both date and time resolved
        if parsed_date and parsed_time:
            comb = datetime.combine(parsed_date, parsed_time).replace(tzinfo=TimezoneService.get_zone_info(tz))
            comb_utc = TimezoneService.to_utc(comb)
            return TemporalResolution(
                original_text=raw,
                status=TemporalResolutionStatus.RESOLVED,
                confidence=1.0,
                timezone=tz,
                resolved_local=TimezoneService.format_local_iso(comb, tz),
                resolved_utc=TimezoneService.format_utc_instant(comb_utc),
                is_ambiguous=False,
                parsed_date=parsed_date,
                parsed_time=parsed_time,
                provenance=TemporalProvenance(
                    original_text=raw,
                    timezone_used=tz,
                    reference_time_utc=ref_utc,
                    parser_version=PARSER_VERSION,
                    resolution_status=TemporalResolutionStatus.RESOLVED,
                    resolution_method="exact_or_relative_combined",
                    confidence=1.0,
                ),
            )

        # If date only resolved without time
        if parsed_date and not parsed_time:
            # Partially resolved (calendar date known, time not specified)
            comb = datetime.combine(parsed_date, time(0, 0)).replace(tzinfo=TimezoneService.get_zone_info(tz))
            comb_utc = TimezoneService.to_utc(comb)
            return TemporalResolution(
                original_text=raw,
                status=TemporalResolutionStatus.PARTIALLY_RESOLVED,
                confidence=0.7,
                timezone=tz,
                resolved_local=TimezoneService.format_local_iso(comb, tz),
                resolved_utc=TimezoneService.format_utc_instant(comb_utc),
                is_ambiguous=False,
                parsed_date=parsed_date,
                parsed_time=None,
                provenance=TemporalProvenance(
                    original_text=raw,
                    timezone_used=tz,
                    reference_time_utc=ref_utc,
                    parser_version=PARSER_VERSION,
                    resolution_status=TemporalResolutionStatus.PARTIALLY_RESOLVED,
                    resolution_method="date_only_unspecified_time",
                    confidence=0.7,
                ),
            )

        # Unrecognized or invalid
        return TemporalResolution(
            original_text=raw,
            status=TemporalResolutionStatus.INVALID,
            confidence=0.0,
            timezone=tz,
            is_ambiguous=False,
            provenance=TemporalProvenance(
                original_text=raw,
                timezone_used=tz,
                reference_time_utc=ref_utc,
                parser_version=PARSER_VERSION,
                resolution_status=TemporalResolutionStatus.INVALID,
                resolution_method="unrecognized_expression",
                confidence=0.0,
            ),
        )
