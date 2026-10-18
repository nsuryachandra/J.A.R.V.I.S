"""Authentication and session management API routes."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_session_id, get_current_user
from app.core.config import get_settings
from app.core.database import get_db_session
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshTokenRequest,
    RegisterRequest,
    SessionResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterRequest,
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Register a new user identity."""
    user = await AuthService.register(
        session=db,
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
        tz=payload.timezone or "Asia/Kolkata",
    )
    return UserResponse(
        id=user.id,
        email=user.email,
        timezone=user.timezone,
        is_active=user.is_active,
        display_name=payload.display_name,
        preferred_address_form="sir",
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Authenticate with email and password to receive JWT access and refresh tokens."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user, user_session, access_token, raw_refresh = await AuthService.login(
        session=db,
        email=payload.email,
        password=payload.password,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in_seconds=settings.access_token_expire_minutes * 60,
        refresh_token=raw_refresh,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
) -> TokenResponse:
    """Rotate refresh session: invalidate old refresh token and issue a fresh token pair."""
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    user, new_session, access_token, new_refresh = await AuthService.refresh_session(
        session=db,
        raw_refresh_token=payload.refresh_token,
        ip_address=client_ip,
        user_agent=user_agent,
    )

    settings = get_settings()
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in_seconds=settings.access_token_expire_minutes * 60,
        refresh_token=new_refresh,
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: User = Depends(get_current_user),
    session_id: UUID = Depends(get_current_session_id),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke the current active session."""
    await AuthService.revoke_session(
        session=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    return {"status": "success", "message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> UserResponse:
    """Retrieve identity profile of current authenticated user."""
    profile_name = current_user.profile.display_name if current_user.profile else "User"
    address_form = current_user.profile.preferred_address_form if current_user.profile else "sir"

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        timezone=current_user.timezone,
        is_active=current_user.is_active,
        display_name=profile_name,
        preferred_address_form=address_form,
    )


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[SessionResponse]:
    """List login sessions for the authenticated user."""
    sessions = await AuthService.list_sessions(session=db, user_id=current_user.id)
    return [
        SessionResponse(
            id=s.id,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            created_at=s.created_at,
            expires_at=s.expires_at,
            is_revoked=s.is_revoked,
        )
        for s in sessions
    ]


@router.post("/sessions/{session_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_session(
    session_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Revoke a specific session belonging to the current user."""
    await AuthService.revoke_session(
        session=db,
        session_id=session_id,
        user_id=current_user.id,
    )
    return {"status": "success", "message": f"Session {session_id} revoked"}
