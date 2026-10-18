"""Database models for Shopping, Booking, & External Actions: Order drafts and transactions."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, utcnow


class OrderDraft(Base, TimestampMixin):
    """Shopping cart, travel booking, or service order draft requiring double approval and idempotency."""

    __tablename__ = "order_drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_type: Mapped[str] = mapped_column(
        String(32),
        default="PURCHASE",  # PURCHASE, FLIGHT_BOOKING, HOTEL_BOOKING, SERVICE_ORDER
        nullable=False,
    )
    merchant: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(8),
        default="USD",
        nullable=False,
    )
    subtotal_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    tax_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    total_amount: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="DRAFT",  # DRAFT, APPROVAL_REQUIRED, EXECUTED, CANCELLED
        nullable=False,
    )
    items: Mapped[str] = mapped_column(
        Text,  # JSON serialized list of line items
        nullable=False,
    )
    delivery_details: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    booking_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )
    approval_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("approval_requests.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    transaction_reference: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
    )
    executed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_order_drafts_user_created", "user_id", "created_at"),
        Index("ix_order_drafts_user_idempotency", "user_id", "idempotency_key"),
    )
