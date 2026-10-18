"""Voice preferences and voice synthesis usage ledger models."""

import uuid
from typing import Optional
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class VoicePreference(Base, TimestampMixin):
    """User-specific voice synthesis preference and configuration."""

    __tablename__ = "voice_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    selected_profile_id: Mapped[str] = mapped_column(
        String(64),
        default="indian_english_male",
        nullable=False,
    )
    speed: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    stability: Mapped[float] = mapped_column(
        Float,
        default=0.5,
        nullable=False,
    )
    similarity_boost: Mapped[float] = mapped_column(
        Float,
        default=0.75,
        nullable=False,
    )
    style: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    voice_enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    privacy_mode: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # Relationships
    user = relationship("User", backref="voice_preference")


class VoiceUsageRecord(Base, TimestampMixin):
    """Immutable ledger of text-to-speech synthesis requests and character consumption."""

    __tablename__ = "voice_usage_records"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        nullable=True,
    )
    profile_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        default="mock",
        nullable=False,
    )
    character_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    duration_seconds: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="SUCCESS",
        nullable=False,
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    user = relationship("User", backref="voice_usage_records")

    __table_args__ = (
        Index("ix_voice_usage_user_created", "user_id", "created_at"),
        Index("ix_voice_usage_user_provider", "user_id", "provider"),
    )
