"""Database models for Communication & Calls: Message drafts, dispatches, and call sessions."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, utcnow


class MessageDraft(Base, TimestampMixin):
    """Email, SMS, or direct messaging draft requiring explicit approval prior to dispatch."""

    __tablename__ = "message_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel: Mapped[str] = mapped_column(
        String(32),
        default="EMAIL",  # EMAIL, SMS, CHAT_MESSAGE
        nullable=False,
    )
    recipient: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    subject: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="DRAFT",  # DRAFT, APPROVAL_REQUIRED, SENT, FAILED, CANCELLED
        nullable=False,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_message_drafts_user_created", "user_id", "created_at"),
        Index("ix_message_drafts_user_status", "user_id", "status"),
    )


class CallSession(Base, TimestampMixin):
    """Telephony call session with briefing notes, recording consent tracking, and transcript summaries."""

    __tablename__ = "call_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_phone: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    recipient_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    purpose: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    briefing_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    recording_consent_disclosed: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PLANNED",  # PLANNED, APPROVAL_REQUIRED, IN_PROGRESS, COMPLETED, CANCELLED
        nullable=False,
    )
    transcript: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    call_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_call_sessions_user_created", "user_id", "created_at"),
    )
