"""Domain contracts for context items, budgeting, assembly, and token allocation."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    SourceReference,
    UserScopedResource,
    VersionedContract,
)


class ContextItemType(str, Enum):
    """Semantic origin and nature of an item assembled into the agent context window."""

    CURRENT_MESSAGE = "CURRENT_MESSAGE"
    RECENT_CONVERSATION = "RECENT_CONVERSATION"
    LONG_TERM_MEMORY = "LONG_TERM_MEMORY"
    TASK = "TASK"
    PROJECT = "PROJECT"
    ROUTINE = "ROUTINE"
    EVENT = "EVENT"
    TOOL_RESULT = "TOOL_RESULT"
    USER_PREFERENCE = "USER_PREFERENCE"
    SYSTEM_POLICY = "SYSTEM_POLICY"
    SAFETY_POLICY = "SAFETY_POLICY"


class ContextSelectionReason(str, Enum):
    """Deterministic justification for including an item in the context window."""

    DIRECT_INPUT = "DIRECT_INPUT"
    RECENT_TEMPORAL = "RECENT_TEMPORAL"
    RELEVANCE_MATCH = "RELEVANCE_MATCH"
    USER_EXPLICIT = "USER_EXPLICIT"
    MANDATORY_SAFETY = "MANDATORY_SAFETY"


class ContextItem(BaseModel):
    """Single discrete factual or conversational element supplied to the model context."""

    model_config = ConfigDict(frozen=True)

    item_id: UUID = Field(default_factory=uuid4)
    item_type: ContextItemType
    source: SourceReference
    content: str = Field(min_length=1)
    token_estimate: int = Field(ge=0, description="Estimated token footprint")
    relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Rank relevance score if retrieved via search",
    )
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.CONVERSATION)
    is_confirmed: bool = Field(
        default=False,
        description="Whether this item is certified confirmed vs inferred",
    )
    selection_reason: ContextSelectionReason


class ContextBudget(BaseModel):
    """Token budget ceiling and component allocations for context window assembly."""

    model_config = ConfigDict(frozen=True)

    max_tokens: int = Field(default=8000, ge=100, le=128000, description="Total budget ceiling")
    allocated_system_tokens: Optional[int] = Field(default=None, ge=0)
    allocated_memory_tokens: Optional[int] = Field(default=None, ge=0)
    allocated_conversation_tokens: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_budget_bounds(self) -> "ContextBudget":
        subtotal = sum(
            x
            for x in [
                self.allocated_system_tokens,
                self.allocated_memory_tokens,
                self.allocated_conversation_tokens,
            ]
            if x is not None
        )
        if subtotal > self.max_tokens:
            raise ValueError(
                f"Sum of allocations ({subtotal}) exceeds max_tokens ({self.max_tokens})."
            )
        return self


class ContextWindow(UserScopedResource):
    """Complete assembled context payload ready for downstream invocation."""

    contract_type: str = Field(default="context.window")
    window_id: UUID = Field(default_factory=uuid4)
    session_id: Optional[UUID] = None
    items: List[ContextItem] = Field(default_factory=list)
    total_estimated_tokens: int = Field(ge=0)
    budget: ContextBudget

    @model_validator(mode="after")
    def validate_token_ceiling(self) -> "ContextWindow":
        computed_tokens = sum(item.token_estimate for item in self.items)
        if self.total_estimated_tokens != computed_tokens:
            raise ValueError(
                f"total_estimated_tokens ({self.total_estimated_tokens}) does not match sum of items ({computed_tokens})."
            )
        if self.total_estimated_tokens > self.budget.max_tokens:
            raise ValueError(
                f"Total context tokens ({self.total_estimated_tokens}) exceeds maximum budget ({self.budget.max_tokens})."
            )
        return self


class ContextAssemblyResult(BaseModel):
    """Output of the context assembly process, including budget and omission diagnostics."""

    model_config = ConfigDict(frozen=True)

    window: ContextWindow
    omitted_items_count: int = Field(ge=0)
    warnings: List[str] = Field(default_factory=list)
