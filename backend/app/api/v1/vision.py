"""REST API router for Vision, Camera, & Screen multimodal inspection and privacy controls."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError, ValidationError
from app.models.user import User
from app.services.vision.schemas import (
    AnalyzeFrameRequest,
    CreateVisionSessionRequest,
    StandaloneVisionAnalysisRequest,
    StandaloneVisionAnalysisResponse,
    TogglePrivacyRequest,
    TogglePrivacyResponse,
    VisionFrameResponse,
    VisionSessionSummary,
)
from app.services.vision.service import VisionService

router = APIRouter(prefix="/vision", tags=["Vision, Camera, & Screen"])
_vision_service = VisionService()


@router.post("/sessions", response_model=VisionSessionSummary)
async def create_vision_session(
    payload: CreateVisionSessionRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VisionSessionSummary:
    """Create a new user-scoped vision capture session with mandatory user consent."""
    current_user, auth_session_id = auth
    try:
        return await _vision_service.create_session(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/sessions", response_model=List[VisionSessionSummary])
async def list_vision_sessions(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[VisionSessionSummary]:
    """List historical vision inspection sessions for the authenticated user."""
    current_user, _ = auth
    return await _vision_service.list_user_sessions(
        db=db,
        user_id=current_user.id,
    )


@router.get("/sessions/{session_id}", response_model=VisionSessionSummary)
async def get_vision_session(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VisionSessionSummary:
    """Retrieve details for a specific vision session."""
    current_user, _ = auth
    try:
        session_rec = await _vision_service.get_session(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
        return VisionSessionSummary(
            id=session_rec.id,
            user_id=session_rec.user_id,
            title=session_rec.title,
            session_type=session_rec.session_type,
            status=session_rec.status,
            privacy_indicator=session_rec.privacy_indicator,
            consent_granted=session_rec.consent_granted,
            device_info=session_rec.device_info,
            frames_count=len(session_rec.frames),
            created_at=session_rec.created_at.isoformat(),
            updated_at=session_rec.updated_at.isoformat(),
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision session not found.")


@router.post("/sessions/{session_id}/toggle", response_model=TogglePrivacyResponse)
async def toggle_vision_privacy(
    session_id: uuid.UUID,
    payload: TogglePrivacyRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> TogglePrivacyResponse:
    """Toggle capture privacy state (MUTE, UNMUTE, STOP) and update visual indicator."""
    current_user, auth_session_id = auth
    try:
        return await _vision_service.toggle_privacy(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision session not found.")
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.post("/sessions/{session_id}/frames", response_model=VisionFrameResponse)
async def analyze_vision_frame(
    session_id: uuid.UUID,
    payload: AnalyzeFrameRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VisionFrameResponse:
    """Ingest, validate, and analyze a visual frame within an active session."""
    current_user, auth_session_id = auth
    try:
        return await _vision_service.analyze_frame(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
            request=payload,
            session_id_auth=auth_session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision session not found.")
    except PermissionDeniedError as err:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(err))
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))


@router.get("/sessions/{session_id}/frames", response_model=List[VisionFrameResponse])
async def list_vision_frames(
    session_id: uuid.UUID,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> List[VisionFrameResponse]:
    """List historical frames and analysis results for session."""
    current_user, _ = auth
    try:
        return await _vision_service.list_frames(
            db=db,
            user_id=current_user.id,
            session_id=session_id,
        )
    except EntityNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vision session not found.")


@router.post("/analyze", response_model=StandaloneVisionAnalysisResponse)
async def analyze_vision_standalone(
    payload: StandaloneVisionAnalysisRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
) -> StandaloneVisionAnalysisResponse:
    """Direct visual inspection without requiring a persistent session."""
    try:
        return await _vision_service.analyze_standalone(request=payload)
    except ValidationError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))
