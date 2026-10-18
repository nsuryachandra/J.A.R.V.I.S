"""SQLAlchemy models for projects, tasks, blockers, and execution state."""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Project(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Top-level initiative grouping related tasks and milestones."""

    __tablename__ = "projects"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        default="ACTIVE",
        nullable=False,
        comment="PLANNING, ACTIVE, ON_HOLD, COMPLETED, CANCELLED, ARCHIVED",
    )
    priority: Mapped[str] = mapped_column(
        String(16),
        default="MEDIUM",
        nullable=False,
        comment="LOW, MEDIUM, HIGH, CRITICAL",
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="PROJECT",
        nullable=False,
    )
    sensitivity: Mapped[int] = mapped_column(
        Integer,
        default=30,  # SensitivityLevel.PRIVATE.value
        nullable=False,
    )

    # Relationships
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="project",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Task.created_at",
    )

    __table_args__ = (
        Index("ix_projects_user_status", "user_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, user_id={self.user_id}, title={self.title}, status={self.status})>"


class Task(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Actionable unit of work with status tracking, blockers, dependencies, and completion evidence."""

    __tablename__ = "tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        index=True,
        default="INBOX",
        nullable=False,
        comment="INBOX, PLANNED, IN_PROGRESS, BLOCKED, WAITING_FOR_USER, WAITING_FOR_APPROVAL, COMPLETED, CANCELLED, ARCHIVED",
    )
    priority: Mapped[str] = mapped_column(
        String(16),
        default="MEDIUM",
        nullable=False,
        comment="LOW, MEDIUM, HIGH, CRITICAL",
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    blocked_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    next_action: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    source_conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    assigned_agent: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="PERSONAL",
        nullable=False,
    )
    sensitivity: Mapped[int] = mapped_column(
        Integer,
        default=30,  # SensitivityLevel.PRIVATE.value
        nullable=False,
    )

    # Complex JSON structures
    blockers: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    dependencies: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
    )
    completion_evidence: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(
        "Project",
        back_populates="tasks",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_user_project", "user_id", "project_id"),
        Index("ix_tasks_user_due", "user_id", "due_at"),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, user_id={self.user_id}, title={self.title}, status={self.status})>"
