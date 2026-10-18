"""SQLAlchemy models for events, recurring routines, routine occurrences, and confirmations."""

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class Event(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Calendar event or discrete temporal occurrence."""

    __tablename__ = "events"

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
    event_type: Mapped[str] = mapped_column(
        String(32),
        default="ONE_TIME",
        nullable=False,
        comment="ONE_TIME, CONFIRMED_HISTORICAL",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PLANNED",
        index=True,
        nullable=False,
        comment="PLANNED, CONFIRMED, COMPLETED, CANCELLED",
    )
    local_start: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Local ISO datetime string e.g. 2026-10-18T14:00:00",
    )
    local_end: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
    )
    utc_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    utc_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Kolkata",
        nullable=False,
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
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_events_user_status", "user_id", "status"),
        Index("ix_events_user_utc_start", "user_id", "utc_start"),
        Index("ix_events_user_title", "user_id", "title"),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, user_id={self.user_id}, title={self.title}, status={self.status})>"


class Routine(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Standing schedule rule defining recurring personal habits and routines."""

    __tablename__ = "routines"

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
    recurrence_rule: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="RFC 5545 recurrence rule string e.g. FREQ=WEEKLY;BYDAY=MO",
    )
    dtstart_local: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Start timestamp in local timezone e.g. 2026-10-18T09:00:00",
    )
    target_time: Mapped[Optional[str]] = mapped_column(
        String(16),
        nullable=True,
        comment="Target local time e.g. 09:00:00",
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Kolkata",
        nullable=False,
    )
    rule_version: Mapped[int] = mapped_column(
        Integer,
        default=1,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
        nullable=False,
    )
    check_in_policy: Mapped[str] = mapped_column(
        String(64),
        default="once_per_occurrence",
        nullable=False,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="PERSONAL",
        nullable=False,
    )
    sensitivity: Mapped[int] = mapped_column(
        Integer,
        default=30,
        nullable=False,
    )
    last_confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    occurrences: Mapped[List["RoutineOccurrence"]] = relationship(
        "RoutineOccurrence",
        back_populates="routine",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="RoutineOccurrence.utc_instant",
    )

    __table_args__ = (
        Index("ix_routines_user_active", "user_id", "is_active"),
        Index("ix_routines_user_title", "user_id", "title"),
    )

    def __repr__(self) -> str:
        return f"<Routine(id={self.id}, user_id={self.user_id}, title={self.title}, active={self.is_active})>"


class RoutineOccurrence(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Discrete temporal occurrence generated from a recurring routine."""

    __tablename__ = "routine_occurrences"

    routine_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("routines.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    occurrence_key: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="Deterministic SHA-256 occurrence identity key",
    )
    scheduled_date: Mapped[str] = mapped_column(
        String(16),
        index=True,
        nullable=False,
        comment="Local date string e.g. 2026-10-19",
    )
    local_time: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        comment="Local ISO datetime e.g. 2026-10-19T09:00:00",
    )
    utc_instant: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
    )
    timezone: Mapped[str] = mapped_column(
        String(64),
        default="Asia/Kolkata",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PLANNED",
        index=True,
        nullable=False,
        comment="PLANNED, PROMPTED, CONFIRMED, COMPLETED, MISSED, SKIPPED, CANCELLED",
    )
    last_check_in_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of check-in to prevent duplicate prompting",
    )
    prompted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    routine: Mapped["Routine"] = relationship(
        "Routine",
        back_populates="occurrences",
        lazy="selectin",
    )
    confirmation: Mapped[Optional["RoutineConfirmation"]] = relationship(
        "RoutineConfirmation",
        back_populates="occurrence",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_routine_occurrences_user_status", "user_id", "status"),
        Index("ix_routine_occurrences_user_date", "user_id", "scheduled_date"),
    )

    def __repr__(self) -> str:
        return f"<RoutineOccurrence(id={self.id}, routine_id={self.routine_id}, date={self.scheduled_date}, status={self.status})>"


class RoutineConfirmation(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Explicit certification of a completed routine occurrence."""

    __tablename__ = "routine_confirmations"

    occurrence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("routine_occurrences.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    confirmed_by: Mapped[str] = mapped_column(
        String(64),
        default="user",
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    occurrence: Mapped["RoutineOccurrence"] = relationship(
        "RoutineOccurrence",
        back_populates="confirmation",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_routine_confirmations_user_confirmed_at", "user_id", "confirmed_at"),
    )

    def __repr__(self) -> str:
        return f"<RoutineConfirmation(id={self.id}, occurrence_id={self.occurrence_id}, confirmed_at={self.confirmed_at})>"
