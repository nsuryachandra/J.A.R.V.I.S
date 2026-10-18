"""REST API router for Communication & Calls: Email, SMS, and Telephony with approval gates."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.user import User
from app.services.communication.schemas import (
    CallSessionResponse,
    CreateMessageDraftRequest,
    InitiateCallRequest,
    InitiateCallResponse,
    MessageDraftResponse,
    PlanCallRequest,
    SendMessageRequest,
    SendMessageResponse,
)
from app.services.communication.service import CommunicationService

router = APIRouter(prefix="/communication", tags=["Communication & Calls"])
_communication_service = CommunicationService()


# --- Message Drafts & Dispatch ---


@router.post("/drafts", response_model=MessageDraftResponse)
async def create_message_draft(
    payload: CreateMessageDraftRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MessageDraftResponse:
    """Create and refine an outbound email, SMS, or chat draft (SAFE action)."""
    current_user, auth_session_id = auth
    try:
        return await _communication_service.create_draft(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/drafts", response_model=List[MessageDraftResponse])
async def list_message_drafts(
    channel_filter: Optional[str] = Query(default=None, alias="channel"),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[MessageDraftResponse]:
    """List message drafts for authenticated user with optional channel and status filters."""
    current_user, _ = auth
    return await _communication_service.list_drafts(
        db=db,
        user_id=current_user.id,
        channel=channel_filter,
        status=status_filter,
    )


@router.get("/drafts/{draft_id}", response_model=MessageDraftResponse)
async def get_message_draft(
    draft_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> MessageDraftResponse:
    """Retrieve details for a specific message draft."""
    current_user, _ = auth
    try:
        d = await _communication_service.get_draft(
            db=db,
            user_id=current_user.id,
            draft_id=draft_id,
        )
        return MessageDraftResponse(
            id=d.id,
            user_id=d.user_id,
            channel=d.channel,
            recipient=d.recipient,
            subject=d.subject,
            body=d.body,
            status=d.status,
            approval_id=d.approval_id,
            sent_at=d.sent_at.isoformat() if d.sent_at else None,
            created_at=d.created_at.isoformat(),
            updated_at=d.updated_at.isoformat(),
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message draft not found.")


@router.post("/drafts/{draft_id}/send", response_model=SendMessageResponse)
async def send_message(
    draft_id: uuid.UUID,
    payload: SendMessageRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> SendMessageResponse:
    """Dispatch outbound message under consequential Policy Broker approval gate."""
    current_user, auth_session_id = auth
    try:
        return await _communication_service.send_message(
            db=db,
            user=current_user,
            draft_id=draft_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message draft not found.")
    except PermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


# --- Telephony Call Sessions ---


@router.post("/calls", response_model=CallSessionResponse)
async def plan_call(
    payload: PlanCallRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CallSessionResponse:
    """Plan call session and compile agenda briefing with consent notice (SAFE action)."""
    current_user, auth_session_id = auth
    try:
        return await _communication_service.plan_call(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/calls", response_model=List[CallSessionResponse])
async def list_calls(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[CallSessionResponse]:
    """List telephony call sessions for authenticated user."""
    current_user, _ = auth
    return await _communication_service.list_calls(
        db=db,
        user_id=current_user.id,
    )


@router.get("/calls/{call_id}", response_model=CallSessionResponse)
async def get_call(
    call_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> CallSessionResponse:
    """Retrieve details for a specific call session."""
    current_user, _ = auth
    try:
        c = await _communication_service.get_call(
            db=db,
            user_id=current_user.id,
            call_id=call_id,
        )
        return CallSessionResponse(
            id=c.id,
            user_id=c.user_id,
            recipient_phone=c.recipient_phone,
            recipient_name=c.recipient_name,
            purpose=c.purpose,
            briefing_notes=c.briefing_notes,
            recording_consent_disclosed=c.recording_consent_disclosed,
            status=c.status,
            transcript=c.transcript,
            call_summary=c.call_summary,
            approval_id=c.approval_id,
            duration_seconds=c.duration_seconds,
            created_at=c.created_at.isoformat(),
            updated_at=c.updated_at.isoformat(),
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call session not found.")


@router.post("/calls/{call_id}/initiate", response_model=InitiateCallResponse)
async def initiate_call(
    call_id: uuid.UUID,
    payload: InitiateCallRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> InitiateCallResponse:
    """Dial out telephony call under consequential Policy Broker approval gate."""
    current_user, auth_session_id = auth
    try:
        return await _communication_service.initiate_call(
            db=db,
            user=current_user,
            call_id=call_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Call session not found.")
    except PermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
