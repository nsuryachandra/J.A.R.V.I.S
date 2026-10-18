"""Coding Agent orchestrator for code inspection, refactoring plans, diff generation, and test validation."""

from pathlib import Path
from typing import Dict, Optional, Tuple
from app.services.coding.diff_engine import DiffEngine
from app.services.coding.inspector import CodeInspector
from app.services.coding.sandbox_runner import SandboxRunner
from app.services.coding.schemas import (
    InspectCodeResponse,
    TestExecutionResponse,
)


class CodingAgent:
    """Specialized agent for codebase inspection, diff creation, and verification."""

    def __init__(self):
        self._inspector = CodeInspector()
        self._diff_engine = DiffEngine()
        self._runner = SandboxRunner()

    def inspect_target(
        self,
        workspace_path: str,
        relative_file_path: Optional[str] = None,
        max_depth: int = 3,
        include_symbols: bool = False,
    ) -> InspectCodeResponse:
        """Inspect directory hierarchy or specific file."""
        return self._inspector.inspect_workspace(
            workspace_path=workspace_path,
            relative_file_path=relative_file_path,
            max_depth=max_depth,
            include_symbols=include_symbols,
        )

    def prepare_change_proposal(
        self,
        workspace_path: str,
        relative_file_path: str,
        proposed_content: str,
    ) -> Tuple[str, str, Dict[str, int]]:
        """Validate path, read original content, generate unified diff, and return stats."""
        target_path = self._inspector.validate_safe_path(workspace_path, relative_file_path)

        original_content = ""
        if target_path.exists():
            original_content = target_path.read_text(encoding="utf-8", errors="replace")

        diff = self._diff_engine.generate_unified_diff(
            target_filename=relative_file_path,
            original_content=original_content,
            proposed_content=proposed_content,
        )
        stats = self._diff_engine.analyze_diff(diff)
        return original_content, diff, stats

    async def execute_tests(
        self,
        workspace_path: str,
        test_target: Optional[str] = None,
        timeout_seconds: int = 15,
    ) -> TestExecutionResponse:
        """Execute sandboxed pytest verification."""
        return await self._runner.run_sandboxed_test(
            cwd=workspace_path,
            test_target=test_target,
            timeout_seconds=timeout_seconds,
        )
