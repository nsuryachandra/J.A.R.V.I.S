"""Database models for Coding Sessions, Change Proposals, and Execution Runs."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, utcnow


class CodingSession(Base, TimestampMixin):
    """User-scoped coding workspace and refactoring session."""

    __tablename__ = "coding_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workspace_path: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="ACTIVE",
        nullable=False,
    )

    # Relationships
    proposals = relationship("CodeChangeProposal", back_populates="session", cascade="all, delete-orphan")
    execution_runs = relationship("CodeExecutionRun", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_coding_sessions_user_created", "user_id", "created_at"),
    )


class CodeChangeProposal(Base, TimestampMixin):
    """Structured code modification proposal with unified diff and approval gating."""

    __tablename__ = "code_change_proposals"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    target_file: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    diff_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    original_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    proposed_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING_APPROVAL",
        nullable=False,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    session = relationship("CodingSession", back_populates="proposals")
    approval = relationship("ApprovalRequest")

    __table_args__ = (
        Index("ix_code_proposals_user_status", "user_id", "status"),
        Index("ix_code_proposals_user_created", "user_id", "created_at"),
    )


class CodeExecutionRun(Base):
    """Sandboxed execution record for test runs, linters, or diagnostics."""

    __tablename__ = "code_execution_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coding_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    command: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    sandbox_dir: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    exit_code: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    stdout: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    stderr: Mapped[str] = mapped_column(
        Text,
        default="",
        nullable=False,
    )
    duration_ms: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    passed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )

    # Relationships
    session = relationship("CodingSession", back_populates="execution_runs")

    __table_args__ = (
        Index("ix_code_execution_runs_user_created", "user_id", "created_at"),
    )
