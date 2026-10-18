"""Database models for Research Sessions, Sources, Facts, Citations, and Document Artifacts."""

import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin


class ResearchSession(Base, TimestampMixin):
    """User-scoped multi-source research investigation session."""

    __tablename__ = "research_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="COMPLETED",
        nullable=False,
    )
    findings_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    sources = relationship("ResearchSource", back_populates="session", cascade="all, delete-orphan")
    facts = relationship("ResearchFact", back_populates="session", cascade="all, delete-orphan")
    documents = relationship("DocumentArtifact", back_populates="session")

    __table_args__ = (
        Index("ix_research_sessions_user_created", "user_id", "created_at"),
    )


class ResearchSource(Base, TimestampMixin):
    """Retrieved and validated external source reference."""

    __tablename__ = "research_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
    )
    url: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    domain: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    snippet: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    credibility_score: Mapped[float] = mapped_column(
        Float,
        default=0.85,
        nullable=False,
    )
    author_or_publisher: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )

    # Relationships
    session = relationship("ResearchSession", back_populates="sources")
    facts = relationship("ResearchFact", back_populates="source")


class ResearchFact(Base, TimestampMixin):
    """Extracted discrete fact with citation attribution and conflict tracking."""

    __tablename__ = "research_facts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("research_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    claim: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    citation_tag: Mapped[str] = mapped_column(
        String(32),
        default="[1]",
        nullable=False,
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        default=0.9,
        nullable=False,
    )
    has_conflict: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    conflict_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    session = relationship("ResearchSession", back_populates="facts")
    source = relationship("ResearchSource", back_populates="facts")


class DocumentArtifact(Base, TimestampMixin):
    """Structured generated document draft with formal citations and exportability."""

    __tablename__ = "document_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("research_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    doc_type: Mapped[str] = mapped_column(
        String(64),
        default="BRIEF",
        nullable=False,
    )
    format: Mapped[str] = mapped_column(
        String(32),
        default="MARKDOWN",
        nullable=False,
    )
    content_markdown: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    word_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    citations_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    session = relationship("ResearchSession", back_populates="documents")

    __table_args__ = (
        Index("ix_document_artifacts_user_created", "user_id", "created_at"),
        Index("ix_document_artifacts_user_type", "user_id", "doc_type"),
    )
