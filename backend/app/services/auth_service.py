"""Authentication service handling registration, password verification, and session rotation."""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.exceptions import (
    AuthenticationError,
    EntityNotFoundError,
    PermissionDeniedError,
    SessionRevokedError,
)
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.base import ensure_utc
from app.models.session import UserSession
from app.models.user import User, UserProfile
from app.services.audit_service import AuditService


class AuthService:
    """Manages identity lifecycle, credential verification, and refresh session rotation."""

    @classmethod
    async def register(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        display_name: str,
        tz: str = "Asia/Kolkata",
    ) -> User:
        """Register a new user with Argon2id or bcrypt hashed password."""
        # Check if email is already registered
        stmt = select(User).where(User.email == email.lower())
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is not None:
            raise AuthenticationError("A user with this email address already exists")

        hashed_pw = hash_password(password)

        user = User(
            email=email.lower(),
            hashed_password=hashed_pw,
            timezone=tz,
            is_active=True,
        )
        session.add(user)
        await session.flush()

        profile = UserProfile(
            user_id=user.id,
            display_name=display_name,
            preferred_address_form="sir",
        )
        session.add(profile)
        await session.flush()

        await AuditService.record_event(
            session=session,
            action_type="USER_REGISTERED",
            decision="ALLOW",
            user_id=user.id,
            details={"email": user.email},
        )

        return user

    @classmethod
    async def login(
        cls,
        session: AsyncSession,
        email: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, UserSession, str, str]:
        """Authenticate user credentials and establish a new refresh session."""
        stmt = select(User).where(User.email == email.lower())
        res = await session.execute(stmt)
        user = res.scalar_one_or_none()

        # Generic authentication failure to prevent user enumeration
        if user is None or not verify_password(password, user.hashed_password):
            await AuditService.record_event(
                session=session,
                action_type="AUTH_LOGIN_FAILED",
                decision="DENY",
                result_status="FAILED",
                error_code="INVALID_CREDENTIALS",
                details={"attempted_email": email.lower()},
                ip_address=ip_address,
            )
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account has been deactivated")

        settings = get_settings()
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=settings.refresh_token_expire_days)

        raw_refresh_token = generate_refresh_token()
        refresh_hash = hash_token(raw_refresh_token)

        user_session = UserSession(
            user_id=user.id,
            refresh_token_hash=refresh_hash,
            ip_address=ip_address,
            user_agent=user_agent,
            expires_at=expires_at,
            is_revoked=False,
        )
        session.add(user_session)
        await session.flush()

        access_token = create_access_token(user.id, user_session.id)

        await AuditService.record_event(
            session=session,
            action_type="AUTH_LOGIN_SUCCESS",
            decision="ALLOW",
            user_id=user.id,
            session_id=user_session.id,
            ip_address=ip_address,
        )

        return user, user_session, access_token, raw_refresh_token

    @classmethod
    async def refresh_session(
        cls,
        session: AsyncSession,
        raw_refresh_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[User, UserSession, str, str]:
        """Rotate refresh session: atomically invalidate previous token and issue a new pair."""
        token_hash = hash_token(raw_refresh_token)

        stmt = select(UserSession).where(UserSession.refresh_token_hash == token_hash)
        res = await session.execute(stmt)
        existing_session = res.scalar_one_or_none()

        if existing_session is None or existing_session.is_revoked:
            # Token reuse detection: if revoked session is attempted, log security event
            await AuditService.record_event(
                session=session,
                action_type="AUTH_REFRESH_REUSED_OR_INVALID",
                decision="DENY",
                result_status="FAILED",
                error_code="REFRESH_TOKEN_REUSED",
                details={"token_hash_prefix": token_hash[:8]},
                ip_address=ip_address,
            )
            raise SessionRevokedError("Invalid or revoked refresh token")

        now = datetime.now(timezone.utc)
        if now >= ensure_utc(existing_session.expires_at):
            existing_session.is_revoked = True
            await session.flush()
            raise SessionRevokedError("Refresh session has expired")

        # Load user
        stmt_user = select(User).where(User.id == existing_session.user_id)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if user is None or not user.is_active:
            raise AuthenticationError("User account unavailable")

        # 1. Atomically invalidate previous refresh session
        existing_session.is_revoked = True

        # 2. Issue new refresh token & session record
        settings = get_settings()
        new_expires_at = now + timedelta(days=settings.refresh_token_expire_days)
        new_raw_refresh = generate_refresh_token()
        new_hash = hash_token(new_raw_refresh)

        new_session = UserSession(
            user_id=user.id,
            refresh_token_hash=new_hash,
            ip_address=ip_address or existing_session.ip_address,
            user_agent=user_agent or existing_session.user_agent,
            expires_at=new_expires_at,
            is_revoked=False,
        )
        session.add(new_session)
        await session.flush()

        new_access_token = create_access_token(user.id, new_session.id)

        await AuditService.record_event(
            session=session,
            action_type="AUTH_REFRESH_ROTATED",
            decision="ALLOW",
            user_id=user.id,
            session_id=new_session.id,
            details={"prior_session_id": str(existing_session.id)},
            ip_address=ip_address,
        )

        return user, new_session, new_access_token, new_raw_refresh

    @classmethod
    async def revoke_session(
        cls,
        session: AsyncSession,
        session_id: UUID,
        user_id: UUID,
    ) -> bool:
        """Revoke an active refresh session."""
        stmt = select(UserSession).where(UserSession.id == session_id)
        res = await session.execute(stmt)
        user_session = res.scalar_one_or_none()

        if user_session is None:
            raise EntityNotFoundError("UserSession", session_id)

        if user_session.user_id != user_id:
            raise PermissionDeniedError("Cannot revoke another user's session")

        user_session.is_revoked = True
        await session.flush()

        await AuditService.record_event(
            session=session,
            action_type="AUTH_SESSION_REVOKED",
            decision="ALLOW",
            user_id=user_id,
            session_id=session_id,
        )
        return True

    @classmethod
    async def list_sessions(
        cls,
        session: AsyncSession,
        user_id: UUID,
    ) -> List[UserSession]:
        """List active sessions belonging to the current user."""
        stmt = (
            select(UserSession)
            .where(UserSession.user_id == user_id)
            .order_by(UserSession.created_at.desc())
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())
