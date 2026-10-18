"""API routes for deterministic temporal parsing, timezone management, and recurrence expansion."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.config import get_settings
from app.core.database import get_db_session
from app.core.exceptions import ValidationError
from app.models.user import User
from app.services.audit_service import AuditService
from app.temporal.schemas import (
    OccurrenceIdentity,
    RecurrenceExpandRequest,
    RecurrenceExpandResponse,
    TemporalResolution,
    TemporalResolveRequest,
    TimezoneInfoResponse,
    TimezoneValidateRequest,
    TimezoneValidateResponse,
)
from app.temporal.resolver import TemporalService
from app.temporal.timezone import TimezoneService, UTC

router = APIRouter(prefix="/temporal", tags=["Temporal Engine"])


@router.post(
    "/resolve",
    response_model=TemporalResolution,
    status_code=status.HTTP_200_OK,
    summary="Resolve natural language temporal expression",
)
async def resolve_temporal_expression(
    payload: TemporalResolveRequest,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> TemporalResolution:
    """
    Resolve natural language temporal expression to normalized UTC and local datetimes.
    Enforces user timezone defaults, deterministic evaluation, and ambiguity detection.
    """
    current_user, session_id = auth_context

    resolution = TemporalService.resolve_expression(
        text=payload.text,
        user=current_user,
        reference_time_utc=payload.reference_time_utc,
        timezone_override=payload.timezone,
    )

    # Audit log resolution action with privacy preservation
    await AuditService.record_event(
        session=db,
        action_type="temporal.resolve",
        decision="ALLOW",
        resource_scope="temporal",
        user_id=current_user.id,
        session_id=session_id,
        details={
            "status": resolution.status.value,
            "timezone": resolution.timezone,
            "is_ambiguous": resolution.is_ambiguous,
            "confidence": resolution.confidence,
        },
    )

    return resolution


@router.post(
    "/expand-recurrence",
    response_model=RecurrenceExpandResponse,
    status_code=status.HTTP_200_OK,
    summary="Expand RFC 5545 recurrence rule within window",
)
async def expand_recurrence(
    payload: RecurrenceExpandRequest,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
) -> RecurrenceExpandResponse:
    """Expand recurrence rule into discrete occurrences with immutable identity keys."""
    current_user, _ = auth_context
    tz = payload.timezone or current_user.timezone

    occurrences = TemporalService.expand_recurrence(
        routine_id=payload.routine_id,
        rule_version=payload.rule_version,
        rrule_string=payload.rrule,
        dtstart_local=payload.dtstart_local,
        timezone=tz,
        max_occurrences=payload.max_occurrences,
        window_start_utc=payload.window_start_utc,
        window_end_utc=payload.window_end_utc,
        exdates=payload.exdates,
    )

    return RecurrenceExpandResponse(
        routine_id=payload.routine_id,
        rule_version=payload.rule_version,
        rrule=payload.rrule,
        timezone=tz,
        occurrences=occurrences,
        total_count=len(occurrences),
    )


@router.get(
    "/timezone",
    response_model=TimezoneInfoResponse,
    status_code=status.HTTP_200_OK,
    summary="Get user timezone and current offsets",
)
async def get_user_timezone_info(
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
) -> TimezoneInfoResponse:
    """Retrieve authenticated user's timezone configuration and offset metadata."""
    current_user, _ = auth_context
    settings = get_settings()
    user_tz = current_user.timezone or settings.timezone

    utc_now = datetime.now(UTC)
    local_now = TimezoneService.to_local(utc_now, user_tz)

    return TimezoneInfoResponse(
        user_timezone=user_tz,
        system_default_timezone=settings.timezone,
        current_utc_offset=TimezoneService.get_utc_offset_str(user_tz, utc_now),
        is_dst=TimezoneService.is_dst(user_tz, utc_now),
        utc_now=TimezoneService.format_utc_instant(utc_now),
        local_now=TimezoneService.format_local_iso(local_now, user_tz),
    )


@router.post(
    "/validate-timezone",
    response_model=TimezoneValidateResponse,
    status_code=status.HTTP_200_OK,
    summary="Validate IANA timezone string",
)
async def validate_timezone(
    payload: TimezoneValidateRequest,
) -> TimezoneValidateResponse:
    """Check if a timezone string is a valid IANA identifier."""
    is_valid = TimezoneService.is_valid_iana_timezone(payload.timezone)
    offset = TimezoneService.get_utc_offset_str(payload.timezone) if is_valid else None
    dst = TimezoneService.is_dst(payload.timezone) if is_valid else None

    return TimezoneValidateResponse(
        timezone=payload.timezone,
        is_valid=is_valid,
        current_utc_offset=offset,
        is_dst=dst,
    )


@router.post(
    "/occurrence-key",
    response_model=OccurrenceIdentity,
    status_code=status.HTTP_200_OK,
    summary="Generate deterministic occurrence key",
)
async def generate_occurrence_key(
    routine_id: UUID,
    rule_version: int,
    local_date_time: str,
    timezone: Optional[str] = None,
    sequence_index: Optional[int] = None,
    auth_context: tuple[User, UUID] = Depends(get_current_user_and_session),
) -> OccurrenceIdentity:
    """Compute SHA-256 occurrence identity key for routine event coordinates."""
    current_user, _ = auth_context
    effective_tz = timezone or current_user.timezone
    return TemporalService.generate_occurrence_identity(
        routine_id=routine_id,
        rule_version=rule_version,
        local_date_time=local_date_time,
        timezone=effective_tz,
        sequence_index=sequence_index,
    )
