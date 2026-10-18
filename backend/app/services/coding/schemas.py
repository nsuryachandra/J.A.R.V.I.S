"""Pydantic contracts and schemas for Coding Agent inspection, diffs, proposals, and sandboxed test runs."""

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CreateCodingSessionRequest(BaseModel):
    """Payload to initialize a coding workspace session."""

    workspace_path: str = Field(min_length=1, max_length=512, description="Absolute or relative workspace path")
    title: str = Field(min_length=1, max_length=255, description="Session title or task name")


class CodingSessionSummary(BaseModel):
    """Overview of a coding session."""

    id: uuid.UUID
    user_id: uuid.UUID
    workspace_path: str
    title: str
    status: str
    proposals_count: int = 0
    created_at: str


class CodeSymbolInfo(BaseModel):
    """Syntactic symbol extracted via AST inspection."""

    name: str
    kind: str = Field(description="class, function, async_function, or variable")
    line_number: int
    docstring: Optional[str] = None
    args: List[str] = []


class CodeFileInfo(BaseModel):
    """Analyzed code file metadata."""

    path: str
    size_bytes: int
    line_count: int
    syntax_valid: bool = True
    syntax_error: Optional[str] = None
    symbols: List[CodeSymbolInfo] = []


class InspectCodeRequest(BaseModel):
    """Request to inspect code structure, symbols, and syntax in a workspace."""

    workspace_path: Optional[str] = Field(default=None, description="Workspace root directory")
    relative_file_path: Optional[str] = Field(default=None, description="Specific file to inspect")
    max_depth: int = Field(default=3, ge=1, le=10)
    include_symbols: bool = False


class InspectCodeResponse(BaseModel):
    """Inspected codebase summary."""

    workspace_path: str
    total_files: int
    files: List[CodeFileInfo]
    summary: str


class ProposeChangeRequest(BaseModel):
    """Request payload to propose code refactoring with unified diff."""

    session_id: uuid.UUID
    target_file: str = Field(min_length=1, max_length=512, description="Target file path")
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(min_length=1, description="Rationale for changes")
    proposed_content: str = Field(min_length=1, description="Complete replacement text")


class CodeChangeProposalResponse(BaseModel):
    """Structured code change proposal with diff and review state."""

    id: uuid.UUID
    session_id: uuid.UUID
    user_id: uuid.UUID
    title: str
    description: str
    target_file: str
    diff_content: str
    status: str
    approval_id: Optional[uuid.UUID] = None
    applied_at: Optional[str] = None
    created_at: str


class ApplyChangeRequest(BaseModel):
    """Request payload to apply an approved code change proposal."""

    proposal_id: uuid.UUID
    approval_id: Optional[uuid.UUID] = Field(default=None, description="ApprovalRequest ID required for consequential application")
    dry_run: bool = False


class ApplyChangeResponse(BaseModel):
    """Outcome of applying a code change proposal."""

    proposal_id: uuid.UUID
    status: str
    applied: bool
    backup_file: Optional[str] = None
    message: str


class RunTestsRequest(BaseModel):
    """Request payload to run sandboxed tests or linter."""

    session_id: Optional[uuid.UUID] = None
    workspace_path: Optional[str] = None
    test_target: Optional[str] = Field(default=None, description="Specific test file or directory")
    timeout_seconds: int = Field(default=15, ge=1, le=60)


class TestExecutionResponse(BaseModel):
    """Outcome and diagnostics from a sandboxed test run."""

    session_id: Optional[uuid.UUID] = None
    command: str
    exit_code: int
    passed: bool
    total_tests: int = 0
    passed_count: int = 0
    failed_count: int = 0
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
