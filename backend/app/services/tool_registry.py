"""Tool registry, risk classifications, explicit moderate policies, and test doubles."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Type
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

class TasksCompleteInput(BaseModel):
    task_id: str
    evidence_type: str = Field(default="USER_CONFIRMATION")
    description: str = Field(min_length=1)

class TasksCompleteOutput(BaseModel):
    task_id: str
    status: str
    completed_at: str

class TasksPendingInput(BaseModel):
    include_yesterday: bool = Field(default=False)

class TasksPendingOutput(BaseModel):
    total_unfinished: int
    in_progress_count: int
    blocked_count: int

class ProjectsCreateInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: Optional[str] = None

class ProjectsCreateOutput(BaseModel):
    project_id: str
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

# 9. MODERATE tool: Complete task with evidence
registry.register(
    ToolDefinition(
        name="tasks.complete",
        version="1.0.0",
        description="Certify and complete a task with evidence",
        risk_class=RiskClass.MODERATE,
        input_schema=TasksCompleteInput,
        output_schema=TasksCompleteOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 10. SAFE tool: Query pending work
registry.register(
    ToolDefinition(
        name="tasks.pending",
        version="1.0.0",
        description="Query pending work, blockers, and upcoming deadlines",
        risk_class=RiskClass.SAFE,
        input_schema=TasksPendingInput,
        output_schema=TasksPendingOutput,
        requires_approval=False,
    )
)

# 11. MODERATE tool: Create project
registry.register(
    ToolDefinition(
        name="projects.create",
        version="1.0.0",
        description="Create an overarching project initiative",
        risk_class=RiskClass.MODERATE,
        input_schema=ProjectsCreateInput,
        output_schema=ProjectsCreateOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

class EventCreateInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    local_start: str = Field(min_length=1)
    local_end: Optional[str] = None
    timezone: str = Field(default="Asia/Kolkata")
    status: str = Field(default="PLANNED")
    description: Optional[str] = None
    notes: Optional[str] = None

class EventCreateOutput(BaseModel):
    event_id: str
    title: str
    status: str
    local_start: str

class RoutineCreateInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    recurrence_rule: str = Field(min_length=1)
    dtstart_local: str = Field(min_length=1)
    target_time: Optional[str] = None
    timezone: str = Field(default="Asia/Kolkata")
    description: Optional[str] = None
    check_in_policy: str = Field(default="once_per_occurrence")

class RoutineCreateOutput(BaseModel):
    routine_id: str
    title: str
    recurrence_rule: str
    rule_version: int

class RoutineConfirmInput(BaseModel):
    occurrence_id: str
    notes: Optional[str] = None
    confirmed_by: str = Field(default="user")

class RoutineConfirmOutput(BaseModel):
    occurrence_id: str
    status: str
    confirmed_at: str

class HabitQueryLastInput(BaseModel):
    habit_name: str = Field(min_length=1)

class HabitQueryLastOutput(BaseModel):
    habit_name: str
    has_confirmed_history: bool
    last_confirmed_date: Optional[str] = None
    formatted_message: str

# 12. MODERATE tool: Create one-time or historical event
registry.register(
    ToolDefinition(
        name="event.create",
        version="1.0.0",
        description="Create a calendar event or confirmed historical record",
        risk_class=RiskClass.MODERATE,
        input_schema=EventCreateInput,
        output_schema=EventCreateOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 13. MODERATE tool: Create recurring routine
registry.register(
    ToolDefinition(
        name="routine.create",
        version="1.0.0",
        description="Create a recurring habit routine with RFC 5545 rules",
        risk_class=RiskClass.MODERATE,
        input_schema=RoutineCreateInput,
        output_schema=RoutineCreateOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 14. MODERATE tool: Confirm occurrence completion
registry.register(
    ToolDefinition(
        name="routine.confirm",
        version="1.0.0",
        description="Certify and confirm completion of a routine occurrence",
        risk_class=RiskClass.MODERATE,
        input_schema=RoutineConfirmInput,
        output_schema=RoutineConfirmOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 15. SAFE tool: Query last habit completion
registry.register(
    ToolDefinition(
        name="habit.query_last",
        version="1.0.0",
        description="Query last confirmed habit occurrence and active routine schedule",
        risk_class=RiskClass.SAFE,
        input_schema=HabitQueryLastInput,
        output_schema=HabitQueryLastOutput,
        requires_approval=False,
    )
)

# --- Phase 8 Schemas ---

class BriefingMorningInput(BaseModel):
    user_id: Optional[str] = None

class BriefingMorningOutput(BaseModel):
    date: str
    greeting: str
    content: str
    events_count: int

class BriefingEveningInput(BaseModel):
    user_id: Optional[str] = None

class BriefingEveningOutput(BaseModel):
    date: str
    greeting: str
    content: str
    completed_count: int

class ProactiveEvaluateInput(BaseModel):
    user_id: Optional[str] = None

class ProactiveEvaluateOutput(BaseModel):
    notifications_generated: int

class NotificationsListInput(BaseModel):
    status: Optional[str] = None
    limit: int = Field(default=20, ge=1, le=100)

class NotificationsListOutput(BaseModel):
    count: int

class NotificationsDismissInput(BaseModel):
    notification_id: str

class NotificationsDismissOutput(BaseModel):
    notification_id: str
    status: str

# 16. SAFE tool: Morning Briefing
registry.register(
    ToolDefinition(
        name="briefing.morning",
        version="1.0.0",
        description="Generate comprehensive morning briefing with calendar, tasks, and routines",
        risk_class=RiskClass.SAFE,
        input_schema=BriefingMorningInput,
        output_schema=BriefingMorningOutput,
        requires_approval=False,
    )
)

# 17. SAFE tool: Evening Briefing
registry.register(
    ToolDefinition(
        name="briefing.evening",
        version="1.0.0",
        description="Generate evening recap with completed work, blockers, and tomorrow's priorities",
        risk_class=RiskClass.SAFE,
        input_schema=BriefingEveningInput,
        output_schema=BriefingEveningOutput,
        requires_approval=False,
    )
)

# 18. MODERATE tool: Proactive Rules Evaluation
registry.register(
    ToolDefinition(
        name="proactive.evaluate",
        version="1.0.0",
        description="Evaluate proactive rules, meal check-ins, and deadlines for user",
        risk_class=RiskClass.MODERATE,
        input_schema=ProactiveEvaluateInput,
        output_schema=ProactiveEvaluateOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 19. SAFE tool: List Proactive Notifications
registry.register(
    ToolDefinition(
        name="notifications.list",
        version="1.0.0",
        description="List proactive notifications, check-ins, and briefings",
        risk_class=RiskClass.SAFE,
        input_schema=NotificationsListInput,
        output_schema=NotificationsListOutput,
        requires_approval=False,
    )
)

# 20. MODERATE tool: Dismiss Notification
registry.register(
    ToolDefinition(
        name="notifications.dismiss",
        version="1.0.0",
        description="Dismiss or acknowledge a proactive notification",
        risk_class=RiskClass.MODERATE,
        input_schema=NotificationsDismissInput,
        output_schema=NotificationsDismissOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# --- Phase 9 Schemas ---

class ModelRouteInput(BaseModel):
    query: str = Field(min_length=1)

class ModelRouteOutput(BaseModel):
    role: str
    model: str
    provider: str

class ModelUsageInput(BaseModel):
    user_id: Optional[str] = None

class ModelUsageOutput(BaseModel):
    total_calls: int
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    avg_latency_ms: float

# 21. SAFE tool: Route Query to Model
registry.register(
    ToolDefinition(
        name="model.route",
        version="1.0.0",
        description="Determine appropriate model role and specific model ID for a user request",
        risk_class=RiskClass.SAFE,
        input_schema=ModelRouteInput,
        output_schema=ModelRouteOutput,
        requires_approval=False,
    )
)

# 22. SAFE tool: Get Token Usage
registry.register(
    ToolDefinition(
        name="model.usage",
        version="1.0.0",
        description="Retrieve token consumption and latency metrics for current user",
        risk_class=RiskClass.SAFE,
        input_schema=ModelUsageInput,
        output_schema=ModelUsageOutput,
        requires_approval=False,
    )
)

# --- Phase 10 Schemas: Voice Integration ---

class VoiceSynthesizeInput(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    profile_id: Optional[str] = None
    speed: Optional[float] = None
    format: str = "mp3"

class VoiceSynthesizeOutput(BaseModel):
    character_count: int
    duration_seconds: float
    profile_id: str
    provider: str

class VoicePreferencesInput(BaseModel):
    selected_profile_id: Optional[str] = None
    speed: Optional[float] = None
    stability: Optional[float] = None
    voice_enabled: Optional[bool] = None
    privacy_mode: Optional[bool] = None

class VoicePreferencesOutput(BaseModel):
    selected_profile_id: str
    speed: float
    voice_enabled: bool
    privacy_mode: bool

class VoicePreferencesGetInput(BaseModel):
    user_id: Optional[str] = None

# 23. SAFE tool: Voice Synthesize
registry.register(
    ToolDefinition(
        name="voice.synthesize",
        version="1.0.0",
        description="Synthesize text to speech using preferred voice profile",
        risk_class=RiskClass.SAFE,
        input_schema=VoiceSynthesizeInput,
        output_schema=VoiceSynthesizeOutput,
        requires_approval=False,
    )
)

# 24. SAFE tool: Get Voice Preferences
registry.register(
    ToolDefinition(
        name="voice.get_preferences",
        version="1.0.0",
        description="Retrieve current user's voice preferences and selected profile",
        risk_class=RiskClass.SAFE,
        input_schema=VoicePreferencesGetInput,
        output_schema=VoicePreferencesOutput,
        requires_approval=False,
    )
)

# 25. MODERATE tool: Update Voice Preferences
registry.register(
    ToolDefinition(
        name="voice.update_preferences",
        version="1.0.0",
        description="Update user's voice profile, speed, and privacy preferences",
        risk_class=RiskClass.MODERATE,
        input_schema=VoicePreferencesInput,
        output_schema=VoicePreferencesOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            sensitive_data_access=False,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# --- Phase 12 Schemas: Research & Writing Agents ---

class ResearchSearchToolInput(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    max_results: int = 5

class ResearchSearchToolOutput(BaseModel):
    total_results: int
    results: List[Dict[str, Any]]

class ResearchExecuteToolInput(BaseModel):
    topic: str = Field(min_length=1, max_length=255)
    query: str = Field(min_length=1, max_length=1000)

class ResearchExecuteToolOutput(BaseModel):
    session_id: str
    topic: str
    findings_count: int
    has_conflicts: bool

class DocumentDraftToolInput(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    doc_type: str = "BRIEF"
    instructions: Optional[str] = None

class DocumentDraftToolOutput(BaseModel):
    document_id: str
    title: str
    word_count: int

# 26. SAFE tool: Research Web Search
registry.register(
    ToolDefinition(
        name="research.search",
        version="1.0.0",
        description="Query and rank approved multi-source research information",
        risk_class=RiskClass.SAFE,
        input_schema=ResearchSearchToolInput,
        output_schema=ResearchSearchToolOutput,
        requires_approval=False,
    )
)

# 27. SAFE tool: Execute Multi-Source Research
registry.register(
    ToolDefinition(
        name="research.execute",
        version="1.0.0",
        description="Execute full research pipeline with fact extraction and conflict detection",
        risk_class=RiskClass.SAFE,
        input_schema=ResearchExecuteToolInput,
        output_schema=ResearchExecuteToolOutput,
        requires_approval=False,
    )
)

# 28. SAFE tool: Draft Document
registry.register(
    ToolDefinition(
        name="document.draft",
        version="1.0.0",
        description="Draft structured document grounded in research findings and citations",
        risk_class=RiskClass.SAFE,
        input_schema=DocumentDraftToolInput,
        output_schema=DocumentDraftToolOutput,
        requires_approval=False,
    )
)

# --- Phase 13 Schemas: Coding Agent ---

class CodeInspectToolInput(BaseModel):
    workspace_path: Optional[str] = None
    relative_file_path: Optional[str] = None
    max_depth: int = 3
    include_symbols: bool = False

class CodeInspectToolOutput(BaseModel):
    workspace_path: str
    total_files: int
    summary: str

class CodeProposeChangeToolInput(BaseModel):
    session_id: str
    target_file: str
    title: str
    description: str
    proposed_content: str

class CodeProposeChangeToolOutput(BaseModel):
    proposal_id: str
    target_file: str
    diff_content: str
    status: str

class CodeApplyChangeToolInput(BaseModel):
    proposal_id: str
    target_file: str
    dry_run: bool = False

class CodeApplyChangeToolOutput(BaseModel):
    proposal_id: str
    status: str
    applied: bool
    message: str

class CodeRunTestsToolInput(BaseModel):
    workspace_path: Optional[str] = None
    test_target: Optional[str] = None
    timeout_seconds: int = 15

class CodeRunTestsToolOutput(BaseModel):
    command: str
    exit_code: int
    passed: bool
    total_tests: int = 0
    passed_count: int = 0
    failed_count: int = 0

# 29. SAFE tool: Code Inspection
registry.register(
    ToolDefinition(
        name="code.inspect",
        version="1.0.0",
        description="Inspect codebase structure, AST symbols, and syntax validity",
        risk_class=RiskClass.SAFE,
        input_schema=CodeInspectToolInput,
        output_schema=CodeInspectToolOutput,
        requires_approval=False,
    )
)

# 30. SAFE tool: Propose Code Change
registry.register(
    ToolDefinition(
        name="code.propose_change",
        version="1.0.0",
        description="Draft code refactoring change proposal with unified git diff",
        risk_class=RiskClass.SAFE,
        input_schema=CodeProposeChangeToolInput,
        output_schema=CodeProposeChangeToolOutput,
        requires_approval=False,
    )
)

# 31. CONSEQUENTIAL tool: Apply Code Change
registry.register(
    ToolDefinition(
        name="code.apply_change",
        version="1.0.0",
        description="Apply approved code refactoring diff directly to target workspace",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=CodeApplyChangeToolInput,
        output_schema=CodeApplyChangeToolOutput,
        requires_approval=True,
    )
)

# 32. SAFE tool: Run Sandboxed Tests
registry.register(
    ToolDefinition(
        name="code.run_tests",
        version="1.0.0",
        description="Execute pytest suite inside isolated sandbox with strict resource bounds",
        risk_class=RiskClass.SAFE,
        input_schema=CodeRunTestsToolInput,
        output_schema=CodeRunTestsToolOutput,
        requires_approval=False,
    )
)

# --- Phase 14 Schemas: Browser & Computer Agent ---

class BrowserNavigateToolInput(BaseModel):
    session_id: str
    url: str

class BrowserNavigateToolOutput(BaseModel):
    session_id: str
    url: str
    title: str
    status: str

class BrowserReadPageToolInput(BaseModel):
    session_id: str

class BrowserReadPageToolOutput(BaseModel):
    session_id: str
    url: str
    title: str
    content: str
    elements_count: int

class BrowserFillFormToolInput(BaseModel):
    session_id: str
    selector: str
    value: str

class BrowserFillFormToolOutput(BaseModel):
    session_id: str
    selector: str
    success: bool

class BrowserScreenshotToolInput(BaseModel):
    session_id: str
    caption: Optional[str] = None

class BrowserScreenshotToolOutput(BaseModel):
    screenshot_id: str
    url: str
    width: int
    height: int

class BrowserSubmitFormToolInput(BaseModel):
    session_id: str
    selector: str
    form_data: Optional[Dict[str, Any]] = None

class BrowserSubmitFormToolOutput(BaseModel):
    session_id: str
    selector: str
    status: str
    new_url: Optional[str] = None

# 33. SAFE tool: Browser Navigate
registry.register(
    ToolDefinition(
        name="browser.navigate",
        version="1.0.0",
        description="Navigate headless browser session to target URL within SSRF-guarded sandbox",
        risk_class=RiskClass.SAFE,
        input_schema=BrowserNavigateToolInput,
        output_schema=BrowserNavigateToolOutput,
        requires_approval=False,
    )
)

# 34. SAFE tool: Browser Read Page
registry.register(
    ToolDefinition(
        name="browser.read_page",
        version="1.0.0",
        description="Extract structured DOM content and interactive elements wrapped in untrusted boundaries",
        risk_class=RiskClass.SAFE,
        input_schema=BrowserReadPageToolInput,
        output_schema=BrowserReadPageToolOutput,
        requires_approval=False,
    )
)

# 35. SAFE tool: Browser Fill Form
registry.register(
    ToolDefinition(
        name="browser.fill_form",
        version="1.0.0",
        description="Fill interactive form input fields with specified value",
        risk_class=RiskClass.SAFE,
        input_schema=BrowserFillFormToolInput,
        output_schema=BrowserFillFormToolOutput,
        requires_approval=False,
    )
)

# 36. SAFE tool: Browser Screenshot
registry.register(
    ToolDefinition(
        name="browser.screenshot",
        version="1.0.0",
        description="Capture visual base64 PNG screenshot for human review and auditing",
        risk_class=RiskClass.SAFE,
        input_schema=BrowserScreenshotToolInput,
        output_schema=BrowserScreenshotToolOutput,
        requires_approval=False,
    )
)

# 37. CONSEQUENTIAL tool: Browser Submit Form
registry.register(
    ToolDefinition(
        name="browser.submit_form",
        version="1.0.0",
        description="Submit interactive form or trigger consequential web action with mandatory human approval",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=BrowserSubmitFormToolInput,
        output_schema=BrowserSubmitFormToolOutput,
        requires_approval=True,
    )
)

# --- Phase 15 Schemas: Vision, Camera, & Screen ---

class VisionAnalyzeImageToolInput(BaseModel):
    image_base64: str
    prompt: Optional[str] = "Describe this image and identify all notable visual elements."

class VisionAnalyzeImageToolOutput(BaseModel):
    analysis_result: str
    detected_objects: List[str] = Field(default_factory=list)
    model_used: str

class VisionCaptureScreenFrameToolInput(BaseModel):
    session_id: str
    prompt: Optional[str] = "Analyze active screen frame content and visible UI."

class VisionCaptureScreenFrameToolOutput(BaseModel):
    frame_id: str
    analysis_result: str
    detected_objects: List[str] = Field(default_factory=list)

class VisionCameraToggleToolInput(BaseModel):
    session_id: str
    action: str = Field(description="'MUTE', 'UNMUTE', or 'STOP'")

class VisionCameraToggleToolOutput(BaseModel):
    session_id: str
    status: str
    privacy_indicator: bool
    message: str

class VisionOcrExtractToolInput(BaseModel):
    image_base64: str

class VisionOcrExtractToolOutput(BaseModel):
    ocr_text: str
    extracted_lines: int

# 38. SAFE tool: Vision Analyze Image
registry.register(
    ToolDefinition(
        name="vision.analyze_image",
        version="1.0.0",
        description="Multimodal image inspection, visual Q&A, and scene description",
        risk_class=RiskClass.SAFE,
        input_schema=VisionAnalyzeImageToolInput,
        output_schema=VisionAnalyzeImageToolOutput,
        requires_approval=False,
    )
)

# 39. MODERATE tool: Vision Capture Screen Frame
registry.register(
    ToolDefinition(
        name="vision.capture_screen_frame",
        version="1.0.0",
        description="Capture and analyze active screen frame with explicit user consent",
        risk_class=RiskClass.MODERATE,
        input_schema=VisionCaptureScreenFrameToolInput,
        output_schema=VisionCaptureScreenFrameToolOutput,
        moderate_policy=ModeratePolicy(
            requires_approval_by_default=False,
            requires_user_capability="screen_capture",
            sensitive_data_access=True,
            write_operation=False,
        ),
        requires_approval=False,
    )
)

# 40. MODERATE tool: Vision Camera Toggle
registry.register(
    ToolDefinition(
        name="vision.camera_toggle",
        version="1.0.0",
        description="Toggle camera stream capture state and update privacy indicator",
        risk_class=RiskClass.MODERATE,
        input_schema=VisionCameraToggleToolInput,
        output_schema=VisionCameraToggleToolOutput,
        moderate_policy=ModeratePolicy(
            requires_approval_by_default=False,
            requires_user_capability="camera_stream",
            sensitive_data_access=False,
            write_operation=True,
        ),
        requires_approval=False,
    )
)

# 41. SAFE tool: Vision OCR Extract
registry.register(
    ToolDefinition(
        name="vision.ocr_extract",
        version="1.0.0",
        description="Extract structured text, receipts, tables, and document content via OCR",
        risk_class=RiskClass.SAFE,
        input_schema=VisionOcrExtractToolInput,
        output_schema=VisionOcrExtractToolOutput,
        requires_approval=False,
    )
)

# --- Phase 16 Schemas: Business & Productivity Agents ---

class BusinessResearchLeadToolInput(BaseModel):
    company_name: str
    industry: Optional[str] = "Technology"
    website: Optional[str] = None

class BusinessResearchLeadToolOutput(BaseModel):
    company_name: str
    lead_score: int
    enrichment_summary: str

class BusinessMonitorCompetitorToolInput(BaseModel):
    name: str
    website: str
    market_segment: Optional[str] = "SaaS"

class BusinessMonitorCompetitorToolOutput(BaseModel):
    name: str
    threat_level: str
    strengths_count: int
    weaknesses_count: int

class BusinessGenerateReportToolInput(BaseModel):
    title: str
    report_type: str = "MARKET_ANALYSIS"
    target_companies: Optional[List[str]] = None
    key_objectives: Optional[str] = None

class BusinessGenerateReportToolOutput(BaseModel):
    title: str
    report_type: str
    summary: str
    recommendations_count: int

class BusinessScoreLeadToolInput(BaseModel):
    company_name: str
    website: Optional[str] = None
    contact_email: Optional[str] = None
    industry: Optional[str] = "Technology"

class BusinessScoreLeadToolOutput(BaseModel):
    company_name: str
    fit_score: int
    qualification_band: str

# 42. SAFE tool: Business Research Lead
registry.register(
    ToolDefinition(
        name="business.research_lead",
        version="1.0.0",
        description="Research firmographic profile, web presence, and strategic fit of prospective business lead",
        risk_class=RiskClass.SAFE,
        input_schema=BusinessResearchLeadToolInput,
        output_schema=BusinessResearchLeadToolOutput,
        requires_approval=False,
    )
)

# 43. SAFE tool: Business Monitor Competitor
registry.register(
    ToolDefinition(
        name="business.monitor_competitor",
        version="1.0.0",
        description="Analyze competitor positioning, strengths, weaknesses, and market threat levels",
        risk_class=RiskClass.SAFE,
        input_schema=BusinessMonitorCompetitorToolInput,
        output_schema=BusinessMonitorCompetitorToolOutput,
        requires_approval=False,
    )
)

# 44. SAFE tool: Business Generate Report
registry.register(
    ToolDefinition(
        name="business.generate_report",
        version="1.0.0",
        description="Compile structured executive business reports, market analyses, and strategic briefs",
        risk_class=RiskClass.SAFE,
        input_schema=BusinessGenerateReportToolInput,
        output_schema=BusinessGenerateReportToolOutput,
        requires_approval=False,
    )
)

# 45. SAFE tool: Business Score Lead
registry.register(
    ToolDefinition(
        name="business.score_lead",
        version="1.0.0",
        description="Calculate quantitative qualification fit score based on firmographic and domain signals",
        risk_class=RiskClass.SAFE,
        input_schema=BusinessScoreLeadToolInput,
        output_schema=BusinessScoreLeadToolOutput,
        requires_approval=False,
    )
)

# --- Phase 17 Schemas: Communication & Calls ---

class CommunicationDraftMessageToolInput(BaseModel):
    channel: str = "EMAIL"
    recipient: str
    body: str
    subject: Optional[str] = None

class CommunicationDraftMessageToolOutput(BaseModel):
    draft_id: str
    channel: str
    recipient: str
    status: str

class CommunicationSendMessageToolInput(BaseModel):
    draft_id: str
    channel: str
    recipient: str

class CommunicationSendMessageToolOutput(BaseModel):
    draft_id: str
    status: str
    sent_at: Optional[str] = None

class CommunicationPrepareCallToolInput(BaseModel):
    recipient_phone: str
    purpose: str
    briefing_notes: Optional[str] = None

class CommunicationPrepareCallToolOutput(BaseModel):
    call_id: str
    recipient_phone: str
    status: str

class CommunicationInitiateCallToolInput(BaseModel):
    call_id: str
    recipient_phone: str
    purpose: str

class CommunicationInitiateCallToolOutput(BaseModel):
    call_id: str
    status: str
    call_summary: Optional[str] = None

# 46. SAFE tool: Communication Draft Message
registry.register(
    ToolDefinition(
        name="communication.draft_message",
        version="1.0.0",
        description="Draft and refine outbound email, SMS, or chat message without sending",
        risk_class=RiskClass.SAFE,
        input_schema=CommunicationDraftMessageToolInput,
        output_schema=CommunicationDraftMessageToolOutput,
        requires_approval=False,
    )
)

# 47. CONSEQUENTIAL tool: Communication Send Message
registry.register(
    ToolDefinition(
        name="communication.send_message",
        version="1.0.0",
        description="Dispatch outbound email or SMS message to external recipient with mandatory human approval",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=CommunicationSendMessageToolInput,
        output_schema=CommunicationSendMessageToolOutput,
        requires_approval=True,
    )
)

# 48. SAFE tool: Communication Prepare Call
registry.register(
    ToolDefinition(
        name="communication.prepare_call",
        version="1.0.0",
        description="Prepare outbound call briefing agenda and recording consent disclosure dossier",
        risk_class=RiskClass.SAFE,
        input_schema=CommunicationPrepareCallToolInput,
        output_schema=CommunicationPrepareCallToolOutput,
        requires_approval=False,
    )
)

# 49. CONSEQUENTIAL tool: Communication Initiate Call
registry.register(
    ToolDefinition(
        name="communication.initiate_call",
        version="1.0.0",
        description="Dial out telephony call to external phone number with mandatory human approval",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=CommunicationInitiateCallToolInput,
        output_schema=CommunicationInitiateCallToolOutput,
        requires_approval=True,
    )
)

# 50. SAFE tool: Commerce Compare Products
class CommerceCompareProductsToolInput(BaseModel):
    query: str
    category: Optional[str] = "General"
    max_price: Optional[float] = None

class CommerceCompareProductsToolOutput(BaseModel):
    query: str
    options_count: int
    best_value_recommendation: str

registry.register(
    ToolDefinition(
        name="commerce.compare_products",
        version="1.0.0",
        description="Search, evaluate, and compare product, travel, or service offerings across merchants",
        risk_class=RiskClass.SAFE,
        input_schema=CommerceCompareProductsToolInput,
        output_schema=CommerceCompareProductsToolOutput,
        requires_approval=False,
    )
)

# 51. SAFE tool: Commerce Create Order Draft
class CommerceCreateOrderDraftToolInput(BaseModel):
    order_type: str
    merchant: str
    title: str
    total_amount: float
    currency: str = "USD"
    idempotency_key: str

class CommerceCreateOrderDraftToolOutput(BaseModel):
    draft_id: str
    status: str
    total_amount: float
    currency: str

registry.register(
    ToolDefinition(
        name="commerce.create_order_draft",
        version="1.0.0",
        description="Prepare an itemized shopping cart, travel booking, or service order draft without executing payment",
        risk_class=RiskClass.SAFE,
        input_schema=CommerceCreateOrderDraftToolInput,
        output_schema=CommerceCreateOrderDraftToolOutput,
        requires_approval=False,
    )
)

# 52. CONSEQUENTIAL tool: Commerce Execute Order
class CommerceExecuteOrderToolInput(BaseModel):
    order_id: str
    merchant: str
    total_amount: float
    currency: str = "USD"
    idempotency_key: str

class CommerceExecuteOrderToolOutput(BaseModel):
    order_id: str
    status: str
    transaction_reference: str
    total_charged: float

registry.register(
    ToolDefinition(
        name="commerce.execute_order",
        version="1.0.0",
        description="Authorize financial transaction, checkout, or booking execution with mandatory human approval",
        risk_class=RiskClass.CONSEQUENTIAL,
        input_schema=CommerceExecuteOrderToolInput,
        output_schema=CommerceExecuteOrderToolOutput,
        requires_approval=True,
        idempotency_required=True,
    )
)

# --- Phase 19 Schemas: Background Scheduling & Jobs ---

class JobsTriggerJobToolInput(BaseModel):
    job_type: str
    idempotency_key: Optional[str] = None
    force: bool = False

class JobsTriggerJobToolOutput(BaseModel):
    job_run_id: str
    job_type: str
    status: str
    duration_ms: Optional[int] = None

class JobsGetStatusToolInput(BaseModel):
    job_type: Optional[str] = None
    limit: int = 10

class JobsGetStatusToolOutput(BaseModel):
    runs_count: int
    latest_status: Optional[str] = None

# 53. MODERATE tool: Jobs Trigger Job
registry.register(
    ToolDefinition(
        name="jobs.trigger_job",
        version="1.0.0",
        description="Trigger background scheduled job (morning briefing, evening summary, consolidation, or tick)",
        risk_class=RiskClass.MODERATE,
        input_schema=JobsTriggerJobToolInput,
        output_schema=JobsTriggerJobToolOutput,
        moderate_policy=ModeratePolicy(
            write_operation=True,
            requires_approval_by_default=False,
        ),
        requires_approval=False,
    )
)

# 54. SAFE tool: Jobs Get Status
registry.register(
    ToolDefinition(
        name="jobs.get_status",
        version="1.0.0",
        description="Inspect background scheduled job execution history, run status, and scheduler health",
        risk_class=RiskClass.SAFE,
        input_schema=JobsGetStatusToolInput,
        output_schema=JobsGetStatusToolOutput,
        requires_approval=False,
    )
)


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry instance."""
    return registry

