"""Common base contracts, identifiers, provenance, pagination, and error representations."""

from datetime import datetime, timezone
from enum import Enum, IntEnum
from typing import Any, Dict, Generic, List, Optional, TypeVar
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SensitivityLevel(IntEnum):
    """Hierarchical sensitivity classification with strict comparative ordering."""

    PUBLIC = 10
    INTERNAL = 20
    PRIVATE = 30
    SENSITIVE = 40
    HIGHLY_SENSITIVE = 50

    def is_less_or_equal(self, other: "SensitivityLevel") -> bool:
        return self.value <= other.value

    def is_strictly_greater(self, other: "SensitivityLevel") -> bool:
        return self.value > other.value


class PrivacyScope(str, Enum):
    """Contextual boundaries preventing accidental disclosure between distinct domains."""

    PERSONAL = "PERSONAL"
    BUSINESS = "BUSINESS"
    PROJECT = "PROJECT"
    CONVERSATION = "CONVERSATION"
    DEVICE = "DEVICE"
    AGENT = "AGENT"
    USER_ONLY = "USER_ONLY"


class Confidence(BaseModel):
    """Normalized confidence score and tier classification."""

    model_config = ConfigDict(frozen=True)

    score: float = Field(ge=0.0, le=1.0, description="Confidence certainty score between 0.0 and 1.0")
    level: str = Field(default="MEDIUM", description="LOW, MEDIUM, HIGH tier")

    @classmethod
    def from_score(cls, score: float) -> "Confidence":
        lvl = "HIGH" if score >= 0.8 else ("MEDIUM" if score >= 0.5 else "LOW")
        return cls(score=score, level=lvl)


class SourceType(str, Enum):
    """Origin category of information or commands entering the system."""

    USER_DIRECT = "USER_DIRECT"
    USER_INFERRED = "USER_INFERRED"
    CONVERSATION = "CONVERSATION"
    TOOL_RESULT = "TOOL_RESULT"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    EXTERNAL_SOURCE = "EXTERNAL_SOURCE"
    AGENT_OUTPUT = "AGENT_OUTPUT"


class SortOrder(str, Enum):
    """Sort direction for queries."""

    ASC = "ASC"
    DESC = "DESC"


class SourceReference(BaseModel):
    """Traceable origin pointer for data ingested or produced by the platform."""

    model_config = ConfigDict(frozen=True)

    source_type: SourceType
    source_id: Optional[str] = None
    message_id: Optional[UUID] = None
    timestamp_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of source event",
    )

    @field_validator("timestamp_utc")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp_utc must be a timezone-aware UTC datetime")
        return v.astimezone(timezone.utc)


class Provenance(BaseModel):
    """Complete lineage and authorship metadata for an entity or action."""

    model_config = ConfigDict(frozen=True)

    source: SourceReference
    author_id: Optional[UUID] = None
    created_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    actor_type: str = Field(default="user", description="user, agent, or system")
    evidence: Optional[str] = None

    @field_validator("created_at_utc")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("created_at_utc must be a timezone-aware UTC datetime")
        return v.astimezone(timezone.utc)


class CorrelationContext(BaseModel):
    """End-to-end request tracing coordinates linking API, agent, tool, and audit actions."""

    model_config = ConfigDict(frozen=True)

    correlation_id: UUID = Field(default_factory=uuid4)
    session_id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    parent_correlation_id: Optional[UUID] = None


class VersionedContract(BaseModel):
    """Base schema establishing formal schema versioning for cross-service contracts."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(
        default="1.0.0",
        pattern=r"^\d+\.\d+\.\d+$",
        description="Semantic version string X.Y.Z",
    )
    contract_type: str = Field(description="Canonical discriminator string")


class UserScopedResource(VersionedContract):
    """Abstract baseline for entities explicitly owned by an authenticated user."""

    resource_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    created_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @field_validator("created_at_utc", "updated_at_utc")
    @classmethod
    def validate_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("Resource datetimes must be timezone-aware UTC")
        return v.astimezone(timezone.utc)


class PaginationRequest(BaseModel):
    """Deterministic pagination and sorting request criteria."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(default=1, ge=1, description="1-indexed page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(default=None, max_length=64)
    sort_order: SortOrder = Field(default=SortOrder.DESC)


T = TypeVar("T")


class PaginationResponse(BaseModel, Generic[T]):
    """Standard paginated collection envelope."""

    model_config = ConfigDict(extra="forbid")

    items: List[T]
    total_count: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1)
    has_more: bool


class ValidationIssue(BaseModel):
    """Single field validation failure detail."""

    model_config = ConfigDict(frozen=True)

    field: str
    issue: str
    rejected_value: Optional[Any] = None


class APIError(BaseModel):
    """Standardized machine-readable error payload."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    correlation_id: Optional[UUID] = None
    validation_issues: List[ValidationIssue] = Field(default_factory=list)


class OperationResult(BaseModel, Generic[T]):
    """Generic outcome container for non-throwing domain operations."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    data: Optional[T] = None
    error: Optional[APIError] = None

    @model_validator(mode="after")
    def validate_error_state(self) -> "OperationResult[T]":
        if self.success is False and self.error is None:
            raise ValueError("OperationResult with success=False must include an APIError")
        if self.success is True and self.error is not None:
            raise ValueError("OperationResult with success=True cannot include an APIError")
        return self
