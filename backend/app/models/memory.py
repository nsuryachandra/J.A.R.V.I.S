"""Memory and MemoryHistory persistence entities for the Personal Context Engine."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Memory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Authoritative long-term declarative memory entity."""

    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    memory_type: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
        comment="SEMANTIC, EPISODIC, PROCEDURAL, TASK_RELATED, TEMPORAL, RELATIONSHIP, SENSITIVE, DEVICE_PREFERENCE",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        default="ACTIVE",
        nullable=False,
        comment="CANDIDATE, CONFIRMED, ACTIVE, SUPERSEDED, EXPIRED, DELETED, REJECTED, DISPUTED",
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
    )
    confirmed_by_user: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    valid_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    superseded_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="PERSONAL",
        index=True,
        nullable=False,
        comment="PERSONAL, BUSINESS, PROJECT, CONVERSATION, DEVICE, AGENT, USER_ONLY",
    )
    sensitivity: Mapped[int] = mapped_column(
        Integer,
        default=30,  # SensitivityLevel.PRIVATE.value
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(
        String(32),
        default="USER_DIRECT",
        nullable=False,
    )
    source_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    source_message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    provenance_evidence: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    embedding_vector: Mapped[Optional[List[float]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Normalized vector embedding representation",
    )

    # Relationships
    history: Mapped[List["MemoryHistory"]] = relationship(
        "MemoryHistory",
        back_populates="memory",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="MemoryHistory.created_at",
    )

    __table_args__ = (
        Index("ix_memories_user_status", "user_id", "status"),
        Index("ix_memories_user_type", "user_id", "memory_type"),
        Index("ix_memories_user_scope", "user_id", "privacy_scope"),
    )

    def __repr__(self) -> str:
        return f"<Memory(id={self.id}, user_id={self.user_id}, type={self.memory_type}, status={self.status})>"


class MemoryHistory(Base, UUIDPrimaryKeyMixin):
    """Append-only audit and revision history for memory records."""

    __tablename__ = "memory_history"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="CREATED, UPDATED, CONFIRMED, CORRECTED, DELETED, EXPIRED",
    )
    previous_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    new_content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    correlation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    # Relationship back to Memory
    memory: Mapped["Memory"] = relationship("Memory", back_populates="history")

    def __repr__(self) -> str:
        return f"<MemoryHistory(id={self.id}, memory_id={self.memory_id}, action={self.action})>"
