"""ApprovalRequest entity for exact-action consequential tool authorizations."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, utcnow


class ApprovalRequest(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """Cryptographically bound, short-lived approval record for consequential actions."""

    __tablename__ = "approval_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("user_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    tool_version: Mapped[str] = mapped_column(
        String(32),
        default="1.0.0",
        nullable=False,
    )
    normalized_arguments: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
    )
    arguments_hash: Mapped[str] = mapped_column(
        String(64),
        index=True,
        nullable=False,
    )
    target_resource: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    risk_class: Mapped[str] = mapped_column(
        String(32),
        default="CONSEQUENTIAL",
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        index=True,
        nullable=False,
    )
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    consumed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    denied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approval_method: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
    )
    created_by_agent_run: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    execution_reference: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )

    # Relationships
    user = relationship("User", backref="approval_requests")
    session = relationship("UserSession", backref="approval_requests")

    def __repr__(self) -> str:
        return f"<ApprovalRequest(id={self.id}, tool={self.tool_name}, status={self.status})>"
