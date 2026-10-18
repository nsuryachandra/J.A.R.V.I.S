"""Pydantic schemas and contracts for Business & Productivity Agent operations."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class CreateLeadRequest(BaseModel):
    """Payload to create or research a prospective business lead."""

    company_name: str = Field(min_length=1, max_length=255)
    contact_name: Optional[str] = Field(default=None, max_length=255)
    contact_email: Optional[str] = Field(default=None, max_length=255)
    website: Optional[str] = Field(default=None, max_length=1024)
    industry: str = Field(default="Technology", max_length=128)
    enrichment_notes: Optional[str] = Field(default=None)
    auto_enrich: bool = Field(default=True, description="Whether to automatically run firmographic enrichment")


class BusinessLeadResponse(BaseModel):
    """Structured response for a business lead prospect."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    company_name: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    website: Optional[str] = None
    industry: str
    lead_score: int
    status: str
    enrichment_notes: Optional[str] = None
    privacy_scope: str
    created_at: str
    updated_at: str


class CreateCompetitorRequest(BaseModel):
    """Payload to register and track a market competitor."""

    name: str = Field(min_length=1, max_length=255)
    website: str = Field(min_length=1, max_length=1024)
    market_segment: str = Field(default="SaaS", max_length=128)
    threat_level: str = Field(default="MEDIUM", description="'LOW', 'MEDIUM', 'HIGH', or 'CRITICAL'")
    strengths: Optional[List[str]] = Field(default=None)
    weaknesses: Optional[List[str]] = Field(default=None)
    pricing_summary: Optional[str] = Field(default=None, max_length=512)
    auto_analyze: bool = Field(default=True, description="Whether to automatically analyze competitive posture")


class CompetitorResponse(BaseModel):
    """Structured response for a tracked competitor."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    website: str
    market_segment: str
    threat_level: str
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    pricing_summary: Optional[str] = None
    last_monitored_at: Optional[str] = None
    privacy_scope: str
    created_at: str
    updated_at: str


class GenerateBusinessReportRequest(BaseModel):
    """Payload to compile an executive market or pipeline report."""

    title: str = Field(min_length=1, max_length=255)
    report_type: str = Field(
        default="MARKET_ANALYSIS",
        description="'MARKET_ANALYSIS', 'COMPETITOR_BRIEF', 'LEAD_PIPELINE', or 'STRATEGIC_PLAN'",
    )
    target_companies: Optional[List[str]] = Field(default=None)
    key_objectives: Optional[str] = Field(default=None)


class BusinessReportResponse(BaseModel):
    """Structured response for a compiled business report."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    report_type: str
    summary: str
    content: str
    recommendations: List[str] = Field(default_factory=list)
    privacy_scope: str
    created_at: str
    updated_at: str
