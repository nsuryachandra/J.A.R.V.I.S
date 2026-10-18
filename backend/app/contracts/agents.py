"""Domain contracts for agent runs, goals, inputs, outputs, delegations, and failures."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.contracts.common import UserScopedResource, VersionedContract


class AgentType(str, Enum):
    """Categorical specialization of an agent in the multi-agent hierarchy."""

    EXECUTIVE = "EXECUTIVE"
    MEMORY = "MEMORY"
    TASK = "TASK"
    DAILY_OPS = "DAILY_OPS"
    RESEARCH = "RESEARCH"
    SYSTEM_SUPERVISOR = "SYSTEM_SUPERVISOR"


class AgentRunStatus(str, Enum):
    """Lifecycle stages of an agent execution run."""

    CREATED = "CREATED"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"


class AgentGoal(BaseModel):
    """Target objective defining the scope of an agent run."""

    model_config = ConfigDict(frozen=True)

    goal_id: UUID = Field(default_factory=uuid4)
    description: str = Field(min_length=1, max_length=2048)
    success_criteria: List[str] = Field(min_length=1)


class AgentInput(BaseModel):
    """Parameters and bound capabilities provided to an agent invocation."""

    model_config = ConfigDict(frozen=True)

    user_id: UUID
    prompt: str = Field(min_length=1)
    context_item_ids: List[UUID] = Field(default_factory=list)
    allowed_tools: List[str] = Field(default_factory=list)
    risk_tier_limit: str = Field(default="SAFE")


class AgentProgressEvent(BaseModel):
    """Incremental progress checkpoint emitted during an agent run."""

    model_config = ConfigDict(frozen=True)

    step_index: int = Field(ge=0)
    stage: str = Field(min_length=1, max_length=128)
    message: str
    timestamp_utc: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AgentRetryPolicy(BaseModel):
    """Fault-tolerance parameters governing automatic run retries."""

    model_config = ConfigDict(frozen=True)

    max_retries: int = Field(default=3, ge=0, le=10)
    backoff_seconds: float = Field(default=1.0, ge=0.1)


class AgentFailure(BaseModel):
    """Detailed error and diagnostics for a failed agent run."""

    model_config = ConfigDict(frozen=True)

    error_code: str
    error_message: str
    failed_step: Optional[int] = None
    recoverable: bool = False


class AgentOutput(BaseModel):
    """Final verified results and artifacts produced by a completed agent run."""

    model_config = ConfigDict(frozen=True)

    result_summary: str = Field(min_length=1)
    artifacts: List[str] = Field(default_factory=list)
    verification_status: str = Field(default="VERIFIED")


class AgentDelegation(BaseModel):
    """Sub-task delegated from a parent agent run to a specialized child agent."""

    model_config = ConfigDict(frozen=True)

    parent_run_id: UUID
    child_agent_type: AgentType
    sub_goal: str = Field(min_length=1)


class AgentRun(UserScopedResource):
    """Root contract representing a single autonomous or interactive agent execution session."""

    contract_type: str = Field(default="agent.run")
    run_id: UUID = Field(default_factory=uuid4)
    parent_run_id: Optional[UUID] = None
    correlation_id: UUID = Field(default_factory=uuid4)
    agent_type: AgentType
    status: AgentRunStatus = Field(default=AgentRunStatus.CREATED)
    goal: AgentGoal
    input: AgentInput
    allowed_tools: List[str] = Field(default_factory=list)
    risk_class: str = Field(default="SAFE")
    started_at_utc: Optional[datetime] = None
    ended_at_utc: Optional[datetime] = None
    progress: List[AgentProgressEvent] = Field(default_factory=list)
    output: Optional[AgentOutput] = None
    failure: Optional[AgentFailure] = None

    @model_validator(mode="after")
    def validate_terminal_state_evidence(self) -> "AgentRun":
        # SUCCEEDED status requires output
        if self.status == AgentRunStatus.SUCCEEDED and self.output is None:
            raise ValueError("AgentRun with status SUCCEEDED must provide an output object.")

        # FAILED status requires failure diagnostic
        if self.status == AgentRunStatus.FAILED and self.failure is None:
            raise ValueError("AgentRun with status FAILED must provide a failure object.")

        # If ended_at_utc is set, it must be >= started_at_utc
        if self.started_at_utc and self.ended_at_utc:
            if self.ended_at_utc < self.started_at_utc:
                raise ValueError("ended_at_utc cannot be prior to started_at_utc.")

        return self
