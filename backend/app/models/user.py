"""User and UserProfile entities for authentication and preferences."""

import uuid
from typing import Optional
from sqlalchemy import Boolean, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Primary user identity entity."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Kolkata",
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # One-to-one relationship with UserProfile
    profile: Mapped[Optional["UserProfile"]] = relationship(
        "UserProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email}, timezone={self.timezone})>"


class UserProfile(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """User preferences, proactive behavior settings, and voice configurations."""

    __tablename__ = "user_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    preferred_address_form: Mapped[str] = mapped_column(
        String(64),
        default="sir",
        nullable=False,
    )
    quiet_hours_start: Mapped[Optional[str]] = mapped_column(
        String(8),
        default="22:00:00",
        nullable=True,
    )
    quiet_hours_end: Mapped[Optional[str]] = mapped_column(
        String(8),
        default="07:00:00",
        nullable=True,
    )
    meal_check_in_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    voice_profile_id: Mapped[str] = mapped_column(
        String(64),
        default="eleven_labs_default_m",
        nullable=False,
    )
    privacy_mode: Mapped[str] = mapped_column(
        String(32),
        default="standard",
        nullable=False,
    )

    # Relationship back to User
    user: Mapped["User"] = relationship("User", back_populates="profile")

    def __repr__(self) -> str:
        return f"<UserProfile(user_id={self.user_id}, display_name={self.display_name})>"
