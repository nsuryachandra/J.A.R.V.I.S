"""Database models for Browser Sessions, Actions, and Visual Screenshots."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import ForeignKey, Index, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, utcnow


class BrowserSession(Base, TimestampMixin):
    """User-scoped headless browser interaction session."""

    __tablename__ = "browser_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        default="Web Interaction Session",
        nullable=False,
    )
    current_url: Mapped[str] = mapped_column(
        String(1024),
        default="about:blank",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",
        nullable=False,
    )
    viewport_width: Mapped[int] = mapped_column(
        Integer,
        default=1280,
        nullable=False,
    )
    viewport_height: Mapped[int] = mapped_column(
        Integer,
        default=800,
        nullable=False,
    )

    # Relationships
    actions = relationship("BrowserAction", back_populates="session", cascade="all, delete-orphan")
    screenshots = relationship("BrowserScreenshot", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_browser_sessions_user_created", "user_id", "created_at"),
    )


class BrowserAction(Base):
    """Recorded browser action with selector, value, and approval tracking."""

    __tablename__ = "browser_actions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("browser_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    target_selector: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    value: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="SUCCESS",
        nullable=False,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    # Relationships
    session = relationship("BrowserSession", back_populates="actions")
    screenshots = relationship("BrowserScreenshot", back_populates="action")

    __table_args__ = (
        Index("ix_browser_actions_session_created", "session_id", "created_at"),
    )


class BrowserScreenshot(Base):
    """Visual page capture log record for auditing and human review."""

    __tablename__ = "browser_screenshots"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("browser_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("browser_actions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    image_base64: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    width: Mapped[int] = mapped_column(
        Integer,
        default=1280,
        nullable=False,
    )
    height: Mapped[int] = mapped_column(
        Integer,
        default=800,
        nullable=False,
    )
    caption: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    # Relationships
    session = relationship("BrowserSession", back_populates="screenshots")
    action = relationship("BrowserAction", back_populates="screenshots")

    __table_args__ = (
        Index("ix_browser_screenshots_session_created", "session_id", "created_at"),
    )
