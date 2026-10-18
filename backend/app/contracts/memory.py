"""Domain contracts for memory candidates, confirmed records, updates, and forget requests."""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.contracts.common import (
    PrivacyScope,
    SensitivityLevel,
    SourceReference,
    SourceType,
    UserScopedResource,
    VersionedContract,
)


class MemoryType(str, Enum):
    """Semantic category distinguishing the operational role of a memory."""

    SEMANTIC = "SEMANTIC"
    EPISODIC = "EPISODIC"
    PROCEDURAL = "PROCEDURAL"
    TASK_RELATED = "TASK_RELATED"
    TEMPORAL = "TEMPORAL"
    RELATIONSHIP = "RELATIONSHIP"
    SENSITIVE = "SENSITIVE"
    DEVICE_PREFERENCE = "DEVICE_PREFERENCE"


class MemoryStatus(str, Enum):
    """Lifecycle and confirmation state of a memory record."""

    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"
    REJECTED = "REJECTED"
    DISPUTED = "DISPUTED"


class MemoryCandidate(VersionedContract):
    """Inferred or proposed fact awaiting verification before promotion to persistent memory."""

    contract_type: str = Field(default="memory.candidate")
    candidate_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=4096)
    confidence: float = Field(ge=0.0, le=1.0, description="Inference certainty score")
    source: SourceReference
    status: MemoryStatus = Field(
        default=MemoryStatus.CANDIDATE,
        description="A proposed candidate must start in CANDIDATE status",
    )
    suggested_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.PERSONAL)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)

    @field_validator("status")
    @classmethod
    def validate_candidate_status(cls, v: MemoryStatus) -> MemoryStatus:
        if v not in (MemoryStatus.CANDIDATE, MemoryStatus.REJECTED):
            raise ValueError(
                f"MemoryCandidate cannot be created with status {v}. Use MemoryRecord for confirmed memories."
            )
        return v


class MemoryRecord(UserScopedResource):
    """Authoritative, confirmed or active long-term memory entity."""

    contract_type: str = Field(default="memory.record")
    memory_id: UUID = Field(default_factory=uuid4)
    memory_type: MemoryType
    content: str = Field(min_length=1, max_length=8192)
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)
    confidence: float = Field(ge=0.0, le=1.0)
    confirmed_by_user: bool = Field(
        default=False,
        description="True if explicitly stated or approved by user",
    )
    valid_from_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    valid_until_utc: Optional[datetime] = None
    superseded_by_id: Optional[UUID] = None
    privacy_scope: PrivacyScope = Field(default=PrivacyScope.PERSONAL)
    sensitivity: SensitivityLevel = Field(default=SensitivityLevel.PRIVATE)
    source: SourceReference

    @model_validator(mode="after")
    def validate_confirmation_and_active_rules(self) -> "MemoryRecord":
        # A memory cannot be active with confidence 0
        if self.status == MemoryStatus.ACTIVE and self.confidence <= 0.0:
            raise ValueError("ACTIVE memory cannot have a confidence score of 0.0")

        # Inferred memories from third-party or autonomous agent must be confirmed by user to become ACTIVE
        if self.source.source_type == SourceType.USER_INFERRED and self.status == MemoryStatus.CONFIRMED:
            if not self.confirmed_by_user:
                raise ValueError("USER_INFERRED memory cannot be CONFIRMED without explicit user confirmation")

        # Expiration check
        if self.valid_until_utc:
            if self.valid_until_utc <= self.valid_from_utc:
                raise ValueError("valid_until_utc must be strictly after valid_from_utc")

        return self


class MemoryUpdate(BaseModel):
    """Specification of mutations applied to an existing memory record."""

    model_config = ConfigDict(extra="forbid")

    content: Optional[str] = Field(default=None, min_length=1, max_length=8192)
    privacy_scope: Optional[PrivacyScope] = None
    sensitivity: Optional[SensitivityLevel] = None
    valid_until_utc: Optional[datetime] = None


class MemoryCorrection(BaseModel):
    """Explicit user correction of inaccurate or superseded memory."""

    model_config = ConfigDict(frozen=True)

    correction_id: UUID = Field(default_factory=uuid4)
    original_memory_id: UUID
    corrected_content: str = Field(min_length=1, max_length=8192)
    reason: str = Field(min_length=1, max_length=1024)
    corrected_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class MemoryForgetRequest(BaseModel):
    """User-initiated right-to-be-forgotten deletion request with audit traceability."""

    model_config = ConfigDict(frozen=True)

    request_id: UUID = Field(default_factory=uuid4)
    memory_id: UUID
    user_id: UUID
    reason: str = Field(min_length=1, max_length=512)
    requested_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    audit_correlation_id: UUID = Field(default_factory=uuid4)


class MemoryConflict(BaseModel):
    """Detected contradiction between memories requiring reconciliation or confirmation."""

    model_config = ConfigDict(frozen=True)

    conflict_id: UUID = Field(default_factory=uuid4)
    existing_memory_id: UUID
    conflicting_candidate_id: UUID
    discrepancy_description: str
    detected_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    resolution_status: str = Field(default="UNRESOLVED")
