"""Append-only audit log entities with cryptographic hash chaining and sequence state."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, UUIDPrimaryKeyMixin, utcnow

GENESIS_HASH = "0" * 64


class AuditLog(Base, UUIDPrimaryKeyMixin):
    """Append-only, tamper-evident audit log record."""

    __tablename__ = "audit_logs"

    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_run_id: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    tool_name: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    tool_version: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    risk_class: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    action_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    resource_scope: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    arguments_hash: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )
    result_status: Mapped[str] = mapped_column(
        String(32),
        default="SUCCESS",
        nullable=False,
    )
    error_code: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        default=dict,
        nullable=False,
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True,
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    previous_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    # Relationships
    user = relationship("User", backref="audit_logs")
    session = relationship("UserSession", backref="audit_logs")
    approval = relationship("ApprovalRequest", backref="audit_logs")

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(seq={self.sequence_number}, action={self.action_type}, decision={self.decision})>"


class AuditLedgerState(Base):
    """Tracks the head of the sequential cryptographic hash chain for serialized concurrency."""

    __tablename__ = "audit_ledger_state"

    id: Mapped[str] = mapped_column(
        String(32),
        primary_key=True,
        default="PRIMARY_LEDGER",
    )
    sequence_number: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
    )
    last_record_hash: Mapped[str] = mapped_column(
        String(64),
        default=GENESIS_HASH,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
        nullable=False,
    )
