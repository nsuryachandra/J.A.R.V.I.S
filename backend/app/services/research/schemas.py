"""Pydantic contracts and schemas for Research and Writing Agents."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Normalized search result from web or knowledge search."""

    title: str
    url: str
    domain: str
    snippet: str
    credibility_score: float = Field(default=0.85, ge=0.0, le=1.0)
    author_or_publisher: Optional[str] = None


class WebSearchRequest(BaseModel):
    """Request payload to query approved research sources."""

    query: str = Field(min_length=1, max_length=500, description="Search terms")
    max_results: int = Field(default=5, ge=1, le=20)
    domain_filter: Optional[str] = None


class WebSearchResponse(BaseModel):
    """Collection of validated search results."""

    query: str
    total_results: int
    results: List[SearchResult]


class ExtractedFact(BaseModel):
    """Discrete factual claim extracted from source material with citation attribution."""

    claim: str
    citation_tag: str = Field(description="[1], [2], etc.")
    source_url: str
    source_title: str
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    has_conflict: bool = False
    conflict_notes: Optional[str] = None


class ResearchExecutionRequest(BaseModel):
    """Payload to trigger end-to-end multi-source research workflow."""

    topic: str = Field(min_length=1, max_length=255)
    query: str = Field(min_length=1, max_length=1000)
    depth: str = Field(default="standard", description="standard, deep, brief")


class ResearchSessionSummary(BaseModel):
    """Summary representation of a research session for lists."""

    id: uuid.UUID
    user_id: uuid.UUID
    topic: str
    query: str
    status: str
    findings_count: int
    summary: Optional[str] = None
    created_at: str


class ResearchBriefResult(BaseModel):
    """Synthesized research brief with full citation lineage."""

    session_id: uuid.UUID
    topic: str
    query: str
    summary: str
    findings_count: int
    facts: List[ExtractedFact]
    sources: List[SearchResult]
    has_unresolved_conflicts: bool


class DraftDocumentRequest(BaseModel):
    """Request payload to generate a structured document draft from research."""

    title: str = Field(min_length=1, max_length=255)
    doc_type: str = Field(default="BRIEF", description="BRIEF, REPORT, SPEC, PRD, SUMMARY")
    session_id: Optional[uuid.UUID] = Field(default=None, description="Optional research session ID to ground document")
    instructions: Optional[str] = Field(default=None, description="Custom drafting instructions or audience")
    format: str = Field(default="MARKDOWN", description="MARKDOWN, HTML, or TEXT")


class DocumentResponse(BaseModel):
    """Saved document artifact representation."""

    id: uuid.UUID
    user_id: uuid.UUID
    session_id: Optional[uuid.UUID] = None
    title: str
    doc_type: str
    format: str
    content_markdown: str
    word_count: int
    citations_count: int
    created_at: str


class DocumentExportResponse(BaseModel):
    """Formatted document export result."""

    document_id: uuid.UUID
    title: str
    format: str
    content_type: str
    exported_content: str
