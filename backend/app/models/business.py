"""Database models for Business & Productivity Agents: Leads, Competitors, and Reports."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, utcnow


class BusinessLead(Base, TimestampMixin):
    """Business prospect or lead enriched with firmographic and market signals."""

    __tablename__ = "business_leads"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    contact_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    contact_email: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    website: Mapped[Optional[str]] = mapped_column(
        String(1024),
        nullable=True,
    )
    industry: Mapped[str] = mapped_column(
        String(128),
        default="Technology",
        nullable=False,
    )
    lead_score: Mapped[int] = mapped_column(
        Integer,
        default=50,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="NEW",  # NEW, RESEARCHED, QUALIFIED, CONTACTED, ARCHIVED
        nullable=False,
    )
    enrichment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="BUSINESS",
        nullable=False,
    )

    __table_args__ = (
        Index("ix_business_leads_user_created", "user_id", "created_at"),
        Index("ix_business_leads_user_status", "user_id", "status"),
    )


class CompetitorProfile(Base, TimestampMixin):
    """Tracked market competitor with capability matrices and threat assessment."""

    __tablename__ = "business_competitors"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    website: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    market_segment: Mapped[str] = mapped_column(
        String(128),
        default="SaaS",
        nullable=False,
    )
    threat_level: Mapped[str] = mapped_column(
        String(32),
        default="MEDIUM",  # LOW, MEDIUM, HIGH, CRITICAL
        nullable=False,
    )
    strengths: Mapped[Optional[str]] = mapped_column(
        Text,  # JSON serialized list of strengths
        nullable=True,
    )
    weaknesses: Mapped[Optional[str]] = mapped_column(
        Text,  # JSON serialized list of weaknesses
        nullable=True,
    )
    pricing_summary: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
    )
    last_monitored_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="BUSINESS",
        nullable=False,
    )

    __table_args__ = (
        Index("ix_business_competitors_user_created", "user_id", "created_at"),
    )


class BusinessReport(Base, TimestampMixin):
    """Executive market brief, competitor review, or lead intelligence report."""

    __tablename__ = "business_reports"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
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
    report_type: Mapped[str] = mapped_column(
        String(64),
        default="MARKET_ANALYSIS",  # MARKET_ANALYSIS, COMPETITOR_BRIEF, LEAD_PIPELINE, STRATEGIC_PLAN
        nullable=False,
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    recommendations: Mapped[Optional[str]] = mapped_column(
        Text,  # JSON serialized list of strategic actions
        nullable=True,
    )
    privacy_scope: Mapped[str] = mapped_column(
        String(32),
        default="BUSINESS",
        nullable=False,
    )

    __table_args__ = (
        Index("ix_business_reports_user_created", "user_id", "created_at"),
    )
