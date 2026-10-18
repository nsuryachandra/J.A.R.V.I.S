"""Authentication and session request/response schemas."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration payload."""
    email: EmailStr
    password: str = Field(min_length=8, description="Password must be at least 8 characters")
    display_name: str = Field(min_length=1, max_length=128)
    timezone: Optional[str] = "Asia/Kolkata"


class LoginRequest(BaseModel):
    """User login credential payload."""
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """JWT access token and refresh token response."""
    access_token: str
    token_type: str = "Bearer"
    expires_in_seconds: int
    refresh_token: str


class RefreshTokenRequest(BaseModel):
    """Token rotation payload."""
    refresh_token: str


class UserResponse(BaseModel):
    """Public user identity response."""
    id: UUID
    email: EmailStr
    timezone: str
    is_active: bool
    display_name: str
    preferred_address_form: str


class SessionResponse(BaseModel):
    """Active user session representation."""
    id: UUID
    ip_address: Optional[str]
    user_agent: Optional[str]
    created_at: datetime
    expires_at: datetime
    is_revoked: bool
