"""Database models for Vision, Camera, and Screen multimodal sessions and frames."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, utcnow


class VisionSession(Base, TimestampMixin):
    """User-scoped vision capture session (Screen share, Camera stream, or Image batch)."""

    __tablename__ = "vision_sessions"

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
        default="Vision Inspection Session",
        nullable=False,
    )
    session_type: Mapped[str] = mapped_column(
        String(32),
        default="IMAGE_UPLOAD",  # IMAGE_UPLOAD, SCREEN_SHARE, CAMERA_STREAM
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",  # ACTIVE, MUTED, STOPPED
        nullable=False,
    )
    privacy_indicator: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    consent_granted: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    device_info: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    frames = relationship("VisionFrame", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_vision_sessions_user_created", "user_id", "created_at"),
    )


class VisionFrame(Base):
    """Individual captured or uploaded visual frame with multimodal analysis and OCR results."""

    __tablename__ = "vision_frames"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vision_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    media_type: Mapped[str] = mapped_column(
        String(64),
        default="image/png",
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
        default=720,
        nullable=False,
    )
    size_bytes: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    query_prompt: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    analysis_result: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    ocr_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    detected_objects: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    # Relationships
    session = relationship("VisionSession", back_populates="frames")

    __table_args__ = (
        Index("ix_vision_frames_session_created", "session_id", "created_at"),
        Index("ix_vision_frames_user_created", "user_id", "created_at"),
    )
