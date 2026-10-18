"""Tool registry, risk classifications, explicit moderate policies, and test doubles."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional, Set, Type
from pydantic import BaseModel, Field


class RiskClass(str, Enum):
    """Logical risk classification for actions and tools."""
    SAFE = "SAFE"
    MODERATE = "MODERATE"
    CONSEQUENTIAL = "CONSEQUENTIAL"


class ModeratePolicy(BaseModel):
    """Explicit governance policy for MODERATE operations."""
    requires_approval_by_default: bool = False
    requires_user_capability: Optional[str] = None
    sensitive_data_access: bool = False
    write_operation: bool = False


@dataclass
class ToolDefinition:
    """Immutable specification and policy metadata for a registered tool."""
    name: str
    version: str
    description: str
    risk_class: RiskClass
    input_schema: Type[BaseModel]
    output_schema: Type[BaseModel]
    moderate_policy: Optional[ModeratePolicy] = None
    required_capabilities: Set[str] = field(default_factory=set)
    allowed_data_scopes: Set[str] = field(default_factory=lambda: {"user"})
    requires_approval: bool = False
    idempotency_required: bool = False
    timeout_seconds: int = 30
    rate_limit_per_minute: int = 60
    is_enabled: bool = True
    audit_required: bool = True

    def __post_init__(self):
        # Consequential actions MUST always require approval
        if self.risk_class == RiskClass.CONSEQUENTIAL:
            self.requires_approval = True
        elif self.risk_class == RiskClass.MODERATE and self.moderate_policy:
            if self.moderate_policy.requires_approval_by_default:
                self.requires_approval = True


class ToolRegistry:
    """Central registry of system tools, schemas, and risk policies."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition into the registry."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Retrieve tool definition by name."""
        return self._tools.get(name)

    def list_tools(self) -> Dict[str, ToolDefinition]:
        """Return all registered tools."""
        return dict(self._tools)

    def is_registered(self, name: str) -> bool:
        """Check if tool name exists in registry."""
        return name in self._tools


# --- Standard Test Double Schemas ---

class ProfileReadInput(BaseModel):
    user_id: Optional[str] = None

class ProfileReadOutput(BaseModel):
    display_name: str
    timezone: str

class TasksReadInput(BaseModel):
    limit: int = Field(default=10, ge=1, le=100)

class TasksReadOutput(BaseModel):
    task_count: int

class TasksCreateInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    priority: str = Field(default="medium")

class TasksCreateOutput(BaseModel):
    task_id: str
    status: str

class DocumentSensitiveReadInput(BaseModel):
    document_id: str

class DocumentSensitiveReadOutput(BaseModel):
    content_preview: str

class EmailSendMockInput(BaseModel):
    recipient: str = Field(min_length=3)
    subject: str = Field(min_length=1)
    body: str = Field(min_length=1)

class EmailSendMockOutput(BaseModel):
    message_id: str
    status: str

class MemorySearchInput(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)

class MemorySearchOutput(BaseModel):
    results_count: int

class MemorySaveInput(BaseModel):
    content: str = Field(min_length=1)
    memory_type: str = Field(default="SEMANTIC")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class MemorySaveOutput(BaseModel):
    memory_id: str
    status: str

class MemoryForgetInput(BaseModel):
    memory_id: str
    reason: str = Field(default="User requested deletion")

class MemoryForgetOutput(BaseModel):
    status: str

# Global registry populated with test doubles
registry = ToolRegistry()

# 1. SAFE tool: Read user profile
registry.register(
    ToolDefinition(
        name="profile.read",
        version="1.0.0",
        description="Read current user profile details",
        risk_class=RiskClass.SAFE,
        input_schema=ProfileReadInput,
        output_schema=ProfileReadOutput,
        requires_approval=False,
    )
)

# 2. MODERATE Read tool: Read user tasks
registry.register(
    ToolDefinition(
        name="tasks.read",
        version="1.0.0",
        description="Read user tasks list",
        risk_class=RiskClass.MODERATE,
        input_schema=TasksReadInput,
        output_schema=TasksReadOutput,
        moderate_policy=ModeratePolicy(
            write_operation=False,
            sensitive_data_access=False,
        ),
        requires_approval=False,
    )
)

# 3. MODERATE Write tool: Create a user task (Reversible internal write)
registry.register(
    ToolDefinition(
        name="tasks.create",
        version="1.0.0",
        description="Create a new task for the user",
        risk_class=RiskClass.MODERATE,
        input_schema=TasksCreateInput,
        output_schema=TasksCreateOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 4. MODERATE Sensitive Data tool: Read confidential user document
registry.register(
    ToolDefinition(
        name="documents.read_sensitive",
        version="1.0.0",
        description="Read a confidential user document",
        risk_class=RiskClass.MODERATE,
        input_schema=DocumentSensitiveReadInput,
        output_schema=DocumentSensitiveReadOutput,
        moderate_policy=ModeratePolicy(
            write_operation=False,
            sensitive_data_access=True,
            requires_user_capability="docs:read_sensitive",
            requires_approval_by_default=False,
        ),
        required_capabilities={"docs:read_sensitive"},
        requires_approval=False,
    )
)

# 5. CONSEQUENTIAL tool: Send email (External side-effect)
registry.register(
    ToolDefinition(
        name="email.send_mock",
        version="1.0.0",
        description="Send an external email (Test Double)",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=EmailSendMockInput,
        output_schema=EmailSendMockOutput,
        required_capabilities={"email:send"},
        requires_approval=True,
    )
)

# 6. SAFE tool: Search memories
registry.register(
    ToolDefinition(
        name="memory.search",
        version="1.0.0",
        description="Semantic retrieval of relevant memories",
        risk_class=RiskClass.SAFE,
        input_schema=MemorySearchInput,
        output_schema=MemorySearchOutput,
        requires_approval=False,
    )
)

# 7. MODERATE tool: Save memory
registry.register(
    ToolDefinition(
        name="memory.save",
        version="1.0.0",
        description="Persist a declarative memory record",
        risk_class=RiskClass.MODERATE,
        input_schema=MemorySaveInput,
        output_schema=MemorySaveOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 8. MODERATE tool: Forget memory
registry.register(
    ToolDefinition(
        name="memory.forget",
        version="1.0.0",
        description="Right-to-be-forgotten deletion of a memory",
        risk_class=RiskClass.MODERATE,
        input_schema=MemoryForgetInput,
        output_schema=MemoryForgetOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=True,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry instance."""
    return registry
