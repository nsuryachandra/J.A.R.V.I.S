"""Database models for Background Scheduling & Jobs: tracking cron and scheduled task execution."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base, TimestampMixin, utcnow


class JobRun(Base, TimestampMixin):
    """Execution record for background cron jobs, briefings, and system routines."""

    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    job_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        comment="MORNING_BRIEFING, EVENING_BRIEFING, NIGHTLY_CONSOLIDATION, SCHEDULER_TICK, STALE_TASK_SWEEP",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="RUNNING",  # RUNNING, SUCCESS, FAILED, SKIPPED
        nullable=False,
        index=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
        comment="Unique execution key to prevent duplicate runs across cron triggers",
    )
    target_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Specific user ID if job ran for single user, or null if system-wide",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    details: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="JSON-serialized execution summary and metrics",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error trace or failure reason if status is FAILED",
    )

    __table_args__ = (
        Index("ix_job_runs_type_started", "job_type", "started_at"),
        Index("ix_job_runs_user_started", "target_user_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<JobRun(id={self.id}, job_type={self.job_type}, status={self.status}, idempotency_key={self.idempotency_key})>"
