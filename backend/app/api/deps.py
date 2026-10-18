"""FastAPI security dependencies for bearer token resolution and tenant identity enforcement."""

from typing import Optional
from uuid import UUID
from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db_session
from app.core.exceptions import AuthenticationError, SessionRevokedError
from app.core.security import decode_access_token
from app.models.session import UserSession
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,
)


async def get_current_user_and_session(
    token: Optional[str] = Depends(oauth2_scheme),
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
) -> tuple[User, UUID]:
    """Resolve authenticated user and active session ID from bearer token."""
    raw_token = token
    if not raw_token and authorization and authorization.startswith("Bearer "):
        raw_token = authorization.split(" ")[1]

    if not raw_token:
        raise AuthenticationError("Authentication required: missing Bearer token")

    payload = decode_access_token(raw_token)
    user_id_str = payload.get("sub")
    session_id_str = payload.get("sid")

    if not user_id_str or not session_id_str:
        raise AuthenticationError("Invalid token claims: missing subject or session ID")

    try:
        user_id = UUID(user_id_str)
        session_id = UUID(session_id_str)
    except ValueError as val_err:
        raise AuthenticationError("Malformed UUID claims in access token") from val_err

    # Check whether the session has been revoked
    stmt_session = select(UserSession).where(UserSession.id == session_id)
    res_session = await db.execute(stmt_session)
    user_session = res_session.scalar_one_or_none()

    if user_session is None or user_session.is_revoked:
        raise SessionRevokedError("Session has been revoked or expired")

    # Fetch User with profile eagerly loaded
    from sqlalchemy.orm import selectinload

    stmt_user = select(User).options(selectinload(User.profile)).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("User account not found")

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    return user, session_id


async def get_current_user(
    auth_tuple: tuple[User, UUID] = Depends(get_current_user_and_session),
) -> User:
    """Dependency yielding the authenticated User entity."""
    return auth_tuple[0]


async def get_current_session_id(
    auth_tuple: tuple[User, UUID] = Depends(get_current_user_and_session),
) -> UUID:
    """Dependency yielding the active session UUID."""
    return auth_tuple[1]
