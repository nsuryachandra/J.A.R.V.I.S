"""SQLAlchemy model for LLM inference usage, token counts, latency tracking, and observability."""

import uuid
from typing import Optional
from sqlalchemy import (
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ModelUsageRecord(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Observability record capturing model calls, token metrics, latency, and provider attribution."""

    __tablename__ = "model_usage_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        index=True,
        nullable=True,
    )
    provider: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        comment="nvidia, mock",
    )
    model_role: Mapped[str] = mapped_column(
        String(32),
        index=True,
        nullable=False,
        comment="fast_chat, reasoning, coding, vision, embedding, classification, summarization",
    )
    model_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        comment="Specific provider model string e.g. meta/llama-3.1-8b-instruct",
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    latency_ms: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    request_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="SUCCESS",
        index=True,
        nullable=False,
        comment="SUCCESS, FAILED, RETRIED, FALLBACK",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="PERSONAL",
        nullable=False,
    )

    __table_args__ = (
        Index("ix_model_usage_user_provider", "user_id", "provider"),
        Index("ix_model_usage_user_role", "user_id", "model_role"),
        Index("ix_model_usage_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ModelUsageRecord(id={self.id}, user_id={self.user_id}, role={self.model_role}, tokens={self.total_tokens})>"
