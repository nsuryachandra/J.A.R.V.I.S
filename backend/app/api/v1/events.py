"""REST API endpoints for calendar events, recurring routines, occurrences, confirmations, and habit queries."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.event import Event, Routine, RoutineConfirmation, RoutineOccurrence
from app.models.user import User
from app.services.event_service import EventService

router = APIRouter(tags=["Events & Routines"])


# -----------------------------------------------------------------------------
# Request & Response Schemas
# -----------------------------------------------------------------------------

class EventCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    local_start: str = Field(min_length=1, description="Local ISO timestamp e.g. 2026-10-18T14:00:00")
    local_end: Optional[str] = None
    timezone: str = Field(default="Asia/Kolkata")
    status: str = Field(default="PLANNED", description="PLANNED, CONFIRMED, COMPLETED")
    event_type: str = Field(default="ONE_TIME", description="ONE_TIME, CONFIRMED_HISTORICAL")
    description: Optional[str] = None
    notes: Optional[str] = None
    privacy_scope: str = Field(default="PERSONAL")
    sensitivity: int = Field(default=30)


class EventConfirmRequest(BaseModel):
    notes: Optional[str] = None


class EventResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str] = None
    event_type: str
    status: str
    local_start: str
    local_end: Optional[str] = None
    utc_start: datetime
    utc_end: Optional[datetime] = None
    timezone: str
    privacy_scope: str
    sensitivity: int
    notes: Optional[str] = None
    confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class RoutineCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    recurrence_rule: str = Field(min_length=1, description="RFC 5545 recurrence rule e.g. FREQ=WEEKLY;BYDAY=MO")
    dtstart_local: str = Field(min_length=1, description="Start time in local timezone e.g. 2026-10-18T09:00:00")
    target_time: Optional[str] = None
    timezone: str = Field(default="Asia/Kolkata")
    description: Optional[str] = None
    check_in_policy: str = Field(default="once_per_occurrence")
    privacy_scope: str = Field(default="PERSONAL")
    sensitivity: int = Field(default=30)
    expand_days: int = Field(default=30, ge=1, le=365)


class RoutineConfirmationResponse(BaseModel):
    id: uuid.UUID
    occurrence_id: uuid.UUID
    user_id: uuid.UUID
    confirmed_at: datetime
    confirmed_by: str
    notes: Optional[str] = None


class RoutineOccurrenceResponse(BaseModel):
    id: uuid.UUID
    routine_id: uuid.UUID
    user_id: uuid.UUID
    occurrence_key: str
    scheduled_date: str
    local_time: str
    utc_instant: datetime
    timezone: str
    status: str
    last_check_in_at: Optional[datetime] = None
    prompted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    confirmation: Optional[RoutineConfirmationResponse] = None
    created_at: datetime
    updated_at: datetime


class RoutineResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: Optional[str] = None
    recurrence_rule: str
    dtstart_local: str
    target_time: Optional[str] = None
    timezone: str
    rule_version: int
    is_active: bool
    check_in_policy: str
    privacy_scope: str
    sensitivity: int
    last_confirmed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    occurrences_count: int = 0


class OccurrenceConfirmRequest(BaseModel):
    confirmed_by: str = Field(default="user")
    notes: Optional[str] = None


class HabitQueryResponse(BaseModel):
    habit_name: str
    has_confirmed_history: bool
    last_confirmed_at: Optional[datetime] = None
    last_confirmed_date: Optional[str] = None
    last_confirmed_type: Optional[str] = None
    has_active_routine: bool
    active_routine_details: Optional[Dict[str, Any]] = None
    current_occurrence_status: str
    formatted_message: str


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _format_event(event: Event) -> EventResponse:
    return EventResponse(
        id=event.id,
        user_id=event.user_id,
        title=event.title,
        description=event.description,
        event_type=event.event_type,
        status=event.status,
        local_start=event.local_start,
        local_end=event.local_end,
        utc_start=event.utc_start,
        utc_end=event.utc_end,
        timezone=event.timezone,
        privacy_scope=event.privacy_scope,
        sensitivity=event.sensitivity,
        notes=event.notes,
        confirmed_at=event.confirmed_at,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def _format_occurrence(occ: RoutineOccurrence) -> RoutineOccurrenceResponse:
    conf = None
    if occ.confirmation:
        conf = RoutineConfirmationResponse(
            id=occ.confirmation.id,
            occurrence_id=occ.confirmation.occurrence_id,
            user_id=occ.confirmation.user_id,
            confirmed_at=occ.confirmation.confirmed_at,
            confirmed_by=occ.confirmation.confirmed_by,
            notes=occ.confirmation.notes,
        )

    return RoutineOccurrenceResponse(
        id=occ.id,
        routine_id=occ.routine_id,
        user_id=occ.user_id,
        occurrence_key=occ.occurrence_key,
        scheduled_date=occ.scheduled_date,
        local_time=occ.local_time,
        utc_instant=occ.utc_instant,
        timezone=occ.timezone,
        status=occ.status,
        last_check_in_at=occ.last_check_in_at,
        prompted_at=occ.prompted_at,
        resolved_at=occ.resolved_at,
        confirmation=conf,
        created_at=occ.created_at,
        updated_at=occ.updated_at,
    )


def _format_routine(routine: Routine) -> RoutineResponse:
    return RoutineResponse(
        id=routine.id,
        user_id=routine.user_id,
        title=routine.title,
        description=routine.description,
        recurrence_rule=routine.recurrence_rule,
        dtstart_local=routine.dtstart_local,
        target_time=routine.target_time,
        timezone=routine.timezone,
        rule_version=routine.rule_version,
        is_active=routine.is_active,
        check_in_policy=routine.check_in_policy,
        privacy_scope=routine.privacy_scope,
        sensitivity=routine.sensitivity,
        last_confirmed_at=routine.last_confirmed_at,
        created_at=routine.created_at,
        updated_at=routine.updated_at,
        occurrences_count=len(routine.occurrences) if routine.occurrences else 0,
    )


# -----------------------------------------------------------------------------
# Endpoints: One-Time Events
# -----------------------------------------------------------------------------

@router.post("/events", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    """Create a discrete calendar event or certified historical event."""
    current_user, session_id = auth
    try:
        event = await EventService.create_one_time_event(
            db=db,
            user_id=current_user.id,
            title=payload.title,
            local_start=payload.local_start,
            local_end=payload.local_end,
            timezone_name=payload.timezone,
            status=payload.status,
            event_type=payload.event_type,
            description=payload.description,
            notes=payload.notes,
            privacy_scope=payload.privacy_scope,
            sensitivity=payload.sensitivity,
            session_id=session_id,
        )
        return _format_event(event)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create event: {exc}")


@router.get("/events", response_model=List[EventResponse])
async def list_events(
    status_filter: Optional[str] = Query(None, alias="status"),
    from_utc: Optional[datetime] = None,
    to_utc: Optional[datetime] = None,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[EventResponse]:
    """List calendar events for current user."""
    current_user, _ = auth
    events = await EventService.list_events(
        db=db,
        user_id=current_user.id,
        status=status_filter,
        from_utc=from_utc,
        to_utc=to_utc,
    )
    return [_format_event(e) for e in events]


@router.get("/events/{event_id}", response_model=EventResponse)
async def get_event(
    event_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    """Get single event by ID with ownership enforcement."""
    current_user, _ = auth
    try:
        event = await EventService.get_event(db, event_id, current_user.id)
        return _format_event(event)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/events/{event_id}/confirm", response_model=EventResponse)
async def confirm_event(
    event_id: uuid.UUID,
    payload: EventConfirmRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> EventResponse:
    """Certify that an event took place, marking status as COMPLETED."""
    current_user, session_id = auth
    try:
        event = await EventService.confirm_event(
            db=db,
            event_id=event_id,
            user_id=current_user.id,
            notes=payload.notes,
            session_id=session_id,
        )
        return _format_event(event)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# -----------------------------------------------------------------------------
# Endpoints: Recurring Routines & Habit Tracking
# -----------------------------------------------------------------------------

@router.post("/routines", response_model=RoutineResponse, status_code=status.HTTP_201_CREATED)
async def create_routine(
    payload: RoutineCreateRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> RoutineResponse:
    """Create a recurring routine and expand initial discrete occurrences."""
    current_user, session_id = auth
    try:
        routine = await EventService.create_routine(
            db=db,
            user_id=current_user.id,
            title=payload.title,
            recurrence_rule=payload.recurrence_rule,
            dtstart_local=payload.dtstart_local,
            target_time=payload.target_time,
            timezone_name=payload.timezone,
            description=payload.description,
            check_in_policy=payload.check_in_policy,
            privacy_scope=payload.privacy_scope,
            sensitivity=payload.sensitivity,
            expand_days=payload.expand_days,
            session_id=session_id,
        )
        return _format_routine(routine)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to create routine: {exc}")


@router.get("/routines", response_model=List[RoutineResponse])
async def list_routines(
    is_active: Optional[bool] = None,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[RoutineResponse]:
    """List recurring routines for current user."""
    current_user, _ = auth
    routines = await EventService.list_routines(db, current_user.id, is_active=is_active)
    return [_format_routine(r) for r in routines]


@router.get("/routines/{routine_id}", response_model=RoutineResponse)
async def get_routine(
    routine_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> RoutineResponse:
    """Get routine details with ownership enforcement."""
    current_user, _ = auth
    try:
        routine = await EventService.get_routine(db, routine_id, current_user.id)
        return _format_routine(routine)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/routines/{routine_id}/expand", response_model=List[RoutineOccurrenceResponse])
async def expand_routine_occurrences(
    routine_id: uuid.UUID,
    days_ahead: int = Query(30, ge=1, le=365),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[RoutineOccurrenceResponse]:
    """Derive and synchronize discrete occurrences for a routine ahead into the future."""
    current_user, _ = auth
    try:
        occs = await EventService.expand_and_sync_occurrences(
            db=db,
            routine_id=routine_id,
            user_id=current_user.id,
            days_ahead=days_ahead,
        )
        return [_format_occurrence(o) for o in occs]
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/routines/{routine_id}/occurrences", response_model=List[RoutineOccurrenceResponse])
async def get_routine_occurrences(
    routine_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[RoutineOccurrenceResponse]:
    """Get all expanded occurrences for a routine."""
    current_user, _ = auth
    try:
        routine = await EventService.get_routine(db, routine_id, current_user.id)
        return [_format_occurrence(o) for o in routine.occurrences]
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# -----------------------------------------------------------------------------
# Endpoints: Discrete Occurrences & Confirmations
# -----------------------------------------------------------------------------

@router.post("/occurrences/{occurrence_id}/confirm", response_model=RoutineOccurrenceResponse)
async def confirm_occurrence(
    occurrence_id: uuid.UUID,
    payload: OccurrenceConfirmRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> RoutineOccurrenceResponse:
    """Certify and confirm completion of a routine occurrence."""
    current_user, session_id = auth
    try:
        occ = await EventService.confirm_occurrence(
            db=db,
            occurrence_id=occurrence_id,
            user_id=current_user.id,
            confirmed_by=payload.confirmed_by,
            notes=payload.notes,
            session_id=session_id,
        )
        return _format_occurrence(occ)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/occurrences/{occurrence_id}/check-in", response_model=RoutineOccurrenceResponse)
async def record_occurrence_check_in(
    occurrence_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> RoutineOccurrenceResponse:
    """Record a check-in on an occurrence to prevent duplicate prompting."""
    current_user, session_id = auth
    try:
        occ = await EventService.record_check_in(
            db=db,
            occurrence_id=occurrence_id,
            user_id=current_user.id,
            session_id=session_id,
        )
        return _format_occurrence(occ)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


# -----------------------------------------------------------------------------
# Endpoints: Habit Inquiry ("When was my last {habit}?", PRD 15.6)
# -----------------------------------------------------------------------------

@router.get("/habits/last", response_model=HabitQueryResponse)
async def query_last_habit(
    habit: str = Query(..., min_length=1, description="Habit title or keyword (e.g. fasting, workout)"),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> HabitQueryResponse:
    """
    Query the last confirmed completion of a habit.
    Accurately distinguishes confirmed completions from unconfirmed routines or today's pending state.
    """
    current_user, _ = auth
    try:
        res = await EventService.query_last_habit(
            db=db,
            user_id=current_user.id,
            habit_name=habit,
        )
        return HabitQueryResponse(**res)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to query habit: {exc}")
