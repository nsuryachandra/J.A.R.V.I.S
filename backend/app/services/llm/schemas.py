"""Pydantic schemas and logical roles for LLM providers, routing, and structured outputs."""

from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field


class ModelRole(str, Enum):
    """Logical model roles defined in PRD Section 9.3."""
    FAST_CHAT = "fast_chat"
    REASONING = "reasoning"
    CODING = "coding"
    VISION = "vision"
    DOCUMENT = "document"
    VOICE_UNDERSTANDING = "voice_understanding"
    SAFETY = "safety"
    SUMMARIZATION = "summarization"
    CLASSIFICATION = "classification"
    EMBEDDING = "embedding"


class LLMMessage(BaseModel):
    """Chat completion message."""
    role: str = Field(description="system, user, assistant, or tool")
    content: str
    name: Optional[str] = None


class LLMUsage(BaseModel):
    """Token consumption metadata."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""
    content: str
    role: str = "assistant"
    model: str
    provider: str
    usage: LLMUsage
    latency_ms: float
    request_id: Optional[str] = None


T = TypeVar("T", bound=BaseModel)


class StructuredLLMResponse(BaseModel, Generic[T]):
    """Structured response validated against a target Pydantic schema."""
    parsed: T
    raw_content: str
    model: str
    provider: str
    usage: LLMUsage
    latency_ms: float


# -----------------------------------------------------------------------------
# Common Structured Output Schemas (PRD 9.6)
# -----------------------------------------------------------------------------

class IntentClassificationResult(BaseModel):
    """Structured output for user request intent classification."""
    intent: str = Field(description="Primary intent category e.g. GREETING, QUERY_TASK, CREATE_EVENT")
    confidence: float = Field(ge=0.0, le=1.0)
    entities: Dict[str, Any] = Field(default_factory=dict)
    requires_tools: bool = False
    risk_level: str = Field(default="SAFE", description="SAFE, MODERATE, CONSEQUENTIAL")


class PlanGenerationResult(BaseModel):
    """Structured output for multi-step task and goal planning."""
    goal: str
    steps: List[str] = Field(default_factory=list)
    estimated_risk: str = Field(default="SAFE")
    required_tools: List[str] = Field(default_factory=list)


class DateInterpretationResult(BaseModel):
    """Structured output for date and temporal parsing."""
    raw_expression: str
    resolved_iso: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    is_ambiguous: bool = False
    clarification_needed: Optional[str] = None
