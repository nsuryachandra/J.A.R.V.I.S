"""Domain contracts for tool proposals, policy decisions, approvals, and execution results."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.contracts.common import VersionedContract


class ExecutionStatus(str, Enum):
    """Lifecycle stages distinguishing proposed, authorized, and executed tool calls."""

    PROPOSED = "PROPOSED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTING = "EXECUTING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DENIED = "DENIED"


class ApprovalReference(BaseModel):
    """Certified linkage to an approval token authorized by an authenticated user."""

    model_config = ConfigDict(frozen=True)

    approval_id: UUID
    approved_by: str = Field(description="User or delegator identifier")
    approved_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    canonical_arguments_hash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 digest of exact approved arguments",
    )


class VerificationEvidence(BaseModel):
    """Cryptographic or sensor proof certifying successful external side-effect execution."""

    model_config = ConfigDict(frozen=True)

    evidence_id: UUID = Field(default_factory=uuid4)
    verification_method: str = Field(description="API_RECEIPT, TRANSACTION_HASH, SYSTEM_STATE_DIFF")
    verified_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    verification_payload: Dict[str, Any] = Field(default_factory=dict)


class ToolCallProposal(VersionedContract):
    """Model-suggested or agent-generated intention to invoke a registered tool."""

    contract_type: str = Field(default="tool.proposal")
    proposal_id: UUID = Field(default_factory=uuid4)
    tool_name: str = Field(min_length=1, max_length=128)
    tool_version: str = Field(default="1.0.0")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    canonical_arguments_hash: str = Field(
        min_length=64,
        max_length=64,
        description="SHA-256 hash of canonical arguments",
    )
    risk_class: str = Field(default="SAFE", description="SAFE, MODERATE, CONSEQUENTIAL")
    proposed_by_agent: str = Field(description="Agent identifier generating proposal")
    status: ExecutionStatus = Field(
        default=ExecutionStatus.PROPOSED,
        description="A proposal must always start in PROPOSED state",
    )

    @model_validator(mode="after")
    def validate_proposal_invariants(self) -> "ToolCallProposal":
        # A proposal cannot claim completion or execution directly
        if self.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.EXECUTING):
            raise ValueError(
                f"A ToolCallProposal cannot have status {self.status.value}. Use ToolExecutionResult for executed actions."
            )
        return self


class ToolCallDecision(BaseModel):
    """Deterministic output of the PolicyBroker evaluating a ToolCallProposal."""

    model_config = ConfigDict(frozen=True)

    decision_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    decision: str = Field(description="ALLOW, DENY, REQUIRE_APPROVAL")
    reason: str
    required_approval_id: Optional[UUID] = None
    evaluated_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class ToolExecutionRequest(BaseModel):
    """Authorized request dispatching an action to the deterministic execution layer."""

    model_config = ConfigDict(frozen=True)

    proposal_id: UUID
    user_id: UUID
    session_id: UUID
    idempotency_key: str = Field(min_length=16, max_length=128)
    approval_ref: Optional[ApprovalReference] = None


class ToolExecutionResult(VersionedContract):
    """Concrete, audited outcome of executing a tool with side-effects."""

    contract_type: str = Field(default="tool.result")
    execution_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    tool_name: str
    status: ExecutionStatus = Field(description="Must be SUCCEEDED, FAILED, or CANCELLED")
    output: Dict[str, Any] = Field(default_factory=dict)
    evidence: Optional[VerificationEvidence] = None
    executed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    duration_ms: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_execution_result_state(self) -> "ToolExecutionResult":
        # Execution result cannot be in PROPOSED or AUTHORIZED state
        if self.status in (ExecutionStatus.PROPOSED, ExecutionStatus.AUTHORIZED, ExecutionStatus.EXECUTING):
            raise ValueError(
                f"ToolExecutionResult must represent completed outcome, not {self.status.value}."
            )
        return self


class ToolExecutionFailure(BaseModel):
    """Structured error diagnostics for an unhandled or rejected tool execution attempt."""

    model_config = ConfigDict(frozen=True)

    failure_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    error_code: str
    error_message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    failed_at_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
