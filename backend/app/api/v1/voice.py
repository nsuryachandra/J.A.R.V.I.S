"""REST API endpoints for Voice Synthesis, Profiles, Preferences, and Usage."""

import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user_and_session
from app.core.database import get_db_session
from app.models.user import User
from app.services.voice.schemas import (
    SynthesizeVoiceRequest,
    VoicePreferencesResponse,
    VoicePreferencesUpdate,
    VoiceProfile,
    VoiceSynthesisResult,
    VoiceUsageMetrics,
)
from app.services.voice.service import VoiceService

router = APIRouter(prefix="/voice", tags=["Voice System & Synthesis"])
_voice_service = VoiceService()


@router.get("/profiles", response_model=List[VoiceProfile])
async def list_voice_profiles(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
) -> List[VoiceProfile]:
    """Retrieve catalog of available voice profiles."""
    return _voice_service.get_profiles()


@router.get("/preferences", response_model=VoicePreferencesResponse)
async def get_user_voice_preferences(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VoicePreferencesResponse:
    """Retrieve authenticated user's current voice preferences."""
    current_user, _ = auth
    return await _voice_service.get_user_preferences(db, current_user.id)


@router.put("/preferences", response_model=VoicePreferencesResponse)
async def update_user_voice_preferences(
    payload: VoicePreferencesUpdate,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VoicePreferencesResponse:
    """Update authenticated user's voice preferences."""
    current_user, session_id = auth
    try:
        return await _voice_service.update_user_preferences(
            db=db,
            user_id=current_user.id,
            payload=payload,
            session_id=session_id,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )


@router.post("/synthesize", response_model=VoiceSynthesisResult)
async def synthesize_speech(
    payload: SynthesizeVoiceRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VoiceSynthesisResult:
    """Synthesize text to speech with performance attribution and usage tracking."""
    current_user, session_id = auth
    try:
        return await _voice_service.synthesize(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id=session_id,
        )
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )


@router.post("/stream")
async def stream_synthesized_speech(
    payload: SynthesizeVoiceRequest,
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> StreamingResponse:
    """Stream synthesized audio chunks directly to client."""
    current_user, session_id = auth
    try:
        stream_gen, content_type = await _voice_service.stream_audio(
            db=db,
            user_id=current_user.id,
            request=payload,
            session_id=session_id,
        )
        return StreamingResponse(stream_gen, media_type=content_type)
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err),
        )


@router.get("/usage", response_model=VoiceUsageMetrics)
async def get_user_voice_usage(
    auth: tuple[User, uuid.UUID] = Depends(get_current_user_and_session),
    db: AsyncSession = Depends(get_db_session),
) -> VoiceUsageMetrics:
    """Retrieve aggregated voice synthesis metrics for the authenticated user."""
    current_user, _ = auth
    return await VoiceService.get_user_usage_metrics(db, current_user.id)
