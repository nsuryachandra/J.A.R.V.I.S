"""Pydantic schemas and typed models for deterministic temporal representation."""

from datetime import date, datetime, time
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
import zoneinfo


class TemporalResolutionStatus(str, Enum):
    """Status of temporal resolution."""

    RESOLVED = "RESOLVED"
    PARTIALLY_RESOLVED = "PARTIALLY_RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    INVALID = "INVALID"
    MISSING_CONTEXT = "MISSING_CONTEXT"


class EventState(str, Enum):
    """Event-state lifecycle boundaries for temporal scheduling and verification."""

    PLANNED = "PLANNED"
    CONFIRMED = "CONFIRMED"
    COMPLETED = "COMPLETED"
    MISSED = "MISSED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"


class ClarificationOption(BaseModel):
    """Candidate interpretation for ambiguous temporal expressions."""

    model_config = ConfigDict(frozen=True)

    option_id: str = Field(description="Unique machine-readable identifier for option")
    label: str = Field(description="Human-friendly label describing option")
    resolved_local: str = Field(description="ISO local datetime representation")
    resolved_utc: str = Field(description="ISO UTC instant representation")


class TemporalAmbiguity(BaseModel):
    """Details when a temporal expression cannot be unambiguously resolved."""

    model_config = ConfigDict(frozen=True)

    reason: str = Field(description="Why the expression is ambiguous")
    clarification_prompt: str = Field(description="Question to ask the user")
    options: List[ClarificationOption] = Field(
        default_factory=list,
        description="Candidate interpretations",
    )


class TemporalProvenance(BaseModel):
    """Audit and provenance metadata for temporal resolutions."""

    model_config = ConfigDict(frozen=True)

    original_text: str
    source_message_id: Optional[str] = None
    user_id: Optional[UUID] = None
    timezone_used: str
    reference_time_utc: datetime
    parser_version: str = "1.0.0"
    resolution_status: TemporalResolutionStatus
    resolution_method: str
    confidence: float = Field(ge=0.0, le=1.0)


class TemporalResolution(BaseModel):
    """Result of resolving a temporal expression."""

    model_config = ConfigDict(frozen=True)

    original_text: str
    status: TemporalResolutionStatus
    confidence: float = Field(ge=0.0, le=1.0)
    timezone: str
    resolved_local: Optional[str] = None
    resolved_utc: Optional[str] = None
    is_ambiguous: bool = False
    ambiguity_details: Optional[TemporalAmbiguity] = None
    provenance: TemporalProvenance
    parsed_date: Optional[date] = None
    parsed_time: Optional[time] = None


class DateRange(BaseModel):
    """Bounded temporal interval with UTC and local boundaries."""

    model_config = ConfigDict(frozen=True)

    start_local: str
    end_local: str
    start_utc: str
    end_utc: str
    timezone: str


class RecurrenceRule(BaseModel):
    """Structured RFC 5545 recurrence rule representation."""

    model_config = ConfigDict(frozen=True)

    freq: str = Field(description="Frequency: DAILY, WEEKLY, MONTHLY, YEARLY")
    interval: int = Field(default=1, ge=1)
    byweekday: Optional[List[str]] = Field(
        default=None,
        description="Weekdays e.g. ['MO', 'FR'] or positional e.g. ['2TU']",
    )
    bymonthday: Optional[List[int]] = Field(default=None)
    count: Optional[int] = Field(default=None, ge=1, le=1000)
    until_utc: Optional[datetime] = None
    until_local: Optional[str] = None
    exdates: List[str] = Field(
        default_factory=list,
        description="ISO date or datetime strings of exclusions",
    )
    rrule_string: Optional[str] = None


class OccurrenceIdentity(BaseModel):
    """Deterministic, immutable identifier for a recurring event occurrence."""

    model_config = ConfigDict(frozen=True)

    occurrence_key: str = Field(description="SHA-256 canonical hash")
    routine_id: UUID
    rule_version: int
    local_date_time: str
    timezone: str
    sequence_index: Optional[int] = None


class RecurrenceOccurrence(BaseModel):
    """Generated single occurrence from recurrence expansion."""

    model_config = ConfigDict(frozen=True)

    occurrence_key: str
    sequence_index: int
    local_time: str
    utc_instant: str
    is_exception: bool = False


# API Request/Response Models


class TemporalResolveRequest(BaseModel):
    """Request to resolve a natural language temporal expression."""

    text: str = Field(min_length=1, max_length=256, description="Temporal expression to parse")
    reference_time_utc: Optional[datetime] = Field(
        default=None,
        description="Optional reference time in UTC for relative resolution (defaults to now)",
    )
    timezone: Optional[str] = Field(
        default=None,
        description="Optional IANA timezone override (must be validated IANA name)",
    )

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                zoneinfo.ZoneInfo(v)
            except Exception as exc:
                raise ValueError(f"Invalid IANA timezone '{v}'") from exc
        return v


class RecurrenceExpandRequest(BaseModel):
    """Request to expand a recurrence rule into occurrences within a window."""

    routine_id: UUID = Field(description="Routine or schedule UUID")
    rule_version: int = Field(default=1, ge=1)
    rrule: str = Field(description="RFC 5545 RRULE string or rule definition")
    dtstart_local: str = Field(
        description="Start date/time in local format: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DD"
    )
    timezone: Optional[str] = Field(
        default=None,
        description="Timezone for local evaluation (defaults to user timezone)",
    )
    max_occurrences: int = Field(
        default=100, ge=1, le=365, description="Upper bound on generated occurrences"
    )
    window_start_utc: Optional[datetime] = Field(
        default=None,
        description="Window start boundary in UTC",
    )
    window_end_utc: Optional[datetime] = Field(
        default=None,
        description="Window end boundary in UTC",
    )
    exdates: List[str] = Field(
        default_factory=list,
        description="Exclusion dates in ISO local or UTC format",
    )

    @field_validator("timezone")
    @classmethod
    def validate_tz(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            try:
                zoneinfo.ZoneInfo(v)
            except Exception as exc:
                raise ValueError(f"Invalid IANA timezone '{v}'") from exc
        return v


class RecurrenceExpandResponse(BaseModel):
    """Response containing generated occurrences."""

    routine_id: UUID
    rule_version: int
    rrule: str
    timezone: str
    occurrences: List[RecurrenceOccurrence]
    total_count: int


class TimezoneValidateRequest(BaseModel):
    """Request to validate an IANA timezone."""

    timezone: str = Field(min_length=1, max_length=64)


class TimezoneValidateResponse(BaseModel):
    """Validation response for timezone."""

    timezone: str
    is_valid: bool
    current_utc_offset: Optional[str] = None
    is_dst: Optional[bool] = None


class TimezoneInfoResponse(BaseModel):
    """Detailed timezone information for authenticated user."""

    user_timezone: str
    system_default_timezone: str
    current_utc_offset: str
    is_dst: bool
    utc_now: str
    local_now: str
