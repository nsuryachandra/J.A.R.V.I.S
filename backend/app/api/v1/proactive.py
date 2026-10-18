"""REST API endpoints for Proactive Intelligence, quiet hours, briefings, and notifications."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.proactive import ProactiveNotification
from app.models.user import User
from app.services.proactive_service import ProactiveService

router = APIRouter(prefix="/proactive", tags=["Proactive Intelligence"])


# -----------------------------------------------------------------------------
# Schemas
# -----------------------------------------------------------------------------

class ProactiveNotificationResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    notification_type: str
    channel: str
    priority: str
    title: str
    content: str
    context_data: Optional[Dict[str, Any]] = None
    status: str
    suppression_reason: Optional[str] = None
    deduplication_key: Optional[str] = None
    dispatched_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class QuietHoursStatusResponse(BaseModel):
    is_active: bool
    quiet_window: str
    timezone: str
    preferred_address_form: str
    meal_check_in_enabled: bool


class BriefingResponse(BaseModel):
    briefing_type: str
    date: str
    formatted_date: str
    timezone: str
    greeting: str
    content: str
    events_today: Optional[List[Dict[str, Any]]] = None
    routines_today: Optional[List[Dict[str, Any]]] = None
    completed_today: Optional[List[Dict[str, Any]]] = None
    pending_work: Optional[Dict[str, Any]] = None
    notification_id: Optional[str] = None


class EvaluateResponse(BaseModel):
    evaluated_at: datetime
    notifications_count: int
    notifications: List[ProactiveNotificationResponse]


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------

def _format_notification(n: ProactiveNotification) -> ProactiveNotificationResponse:
    return ProactiveNotificationResponse(
        id=n.id,
        user_id=n.user_id,
        notification_type=n.notification_type,
        channel=n.channel,
        priority=n.priority,
        title=n.title,
        content=n.content,
        context_data=n.context_data,
        status=n.status,
        suppression_reason=n.suppression_reason,
        deduplication_key=n.deduplication_key,
        dispatched_at=n.dispatched_at,
        read_at=n.read_at,
        dismissed_at=n.dismissed_at,
        created_at=n.created_at,
        updated_at=n.updated_at,
    )


# -----------------------------------------------------------------------------
# Briefing Endpoints
# -----------------------------------------------------------------------------

@router.get("/briefing/morning", response_model=BriefingResponse)
async def get_morning_briefing(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BriefingResponse:
    """Generate or retrieve morning briefing for the authenticated user."""
    current_user, session_id = auth
    res = await ProactiveService.generate_morning_briefing(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
    )
    return BriefingResponse(**res)


@router.get("/briefing/evening", response_model=BriefingResponse)
async def get_evening_briefing(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> BriefingResponse:
    """Generate or retrieve evening briefing for the authenticated user."""
    current_user, session_id = auth
    res = await ProactiveService.generate_evening_briefing(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
    )
    return BriefingResponse(**res)


# -----------------------------------------------------------------------------
# Evaluation & Notification Endpoints
# -----------------------------------------------------------------------------

@router.post("/evaluate", response_model=EvaluateResponse)
async def evaluate_proactive_rules(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> EvaluateResponse:
    """Trigger proactive rules evaluation cycle (meal check-in, deadlines)."""
    current_user, session_id = auth
    notifications = await ProactiveService.evaluate_proactive_rules(
        db=db,
        user_id=current_user.id,
        session_id=session_id,
    )
    formatted = [_format_notification(n) for n in notifications]
    return EvaluateResponse(
        evaluated_at=datetime.utcnow(),
        notifications_count=len(formatted),
        notifications=formatted,
    )


@router.get("/notifications", response_model=List[ProactiveNotificationResponse])
async def list_notifications(
    status_filter: Optional[str] = Query(None, alias="status"),
    notification_type: Optional[str] = Query(None, alias="type"),
    limit: int = Query(50, ge=1, le=100),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[ProactiveNotificationResponse]:
    """List proactive notifications with user isolation and optional filtering."""
    current_user, _ = auth
    notifications = await ProactiveService.list_notifications(
        db=db,
        user_id=current_user.id,
        status=status_filter,
        notification_type=notification_type,
        limit=limit,
    )
    return [_format_notification(n) for n in notifications]


@router.post("/notifications/{notification_id}/dismiss", response_model=ProactiveNotificationResponse)
async def dismiss_notification(
    notification_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ProactiveNotificationResponse:
    """Dismiss a proactive notification."""
    current_user, _ = auth
    try:
        n = await ProactiveService.dismiss_notification(db, notification_id, current_user.id)
        return _format_notification(n)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.post("/notifications/{notification_id}/read", response_model=ProactiveNotificationResponse)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> ProactiveNotificationResponse:
    """Mark a proactive notification as read."""
    current_user, _ = auth
    try:
        n = await ProactiveService.mark_as_read(db, notification_id, current_user.id)
        return _format_notification(n)
    except EntityNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))


@router.get("/quiet-hours", response_model=QuietHoursStatusResponse)
async def get_quiet_hours_status(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> QuietHoursStatusResponse:
    """Check current quiet hours status in the user's timezone."""
    current_user, _ = auth
    user, profile = await ProactiveService.get_user_and_profile(db, current_user.id)
    is_active, window_desc = ProactiveService.is_quiet_hours_active(profile, user.timezone)
    return QuietHoursStatusResponse(
        is_active=is_active,
        quiet_window=window_desc,
        timezone=user.timezone,
        preferred_address_form=profile.preferred_address_form or "neutral",
        meal_check_in_enabled=profile.meal_check_in_enabled,
    )
