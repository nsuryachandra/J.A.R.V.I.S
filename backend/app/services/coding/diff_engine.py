"""Unified diff generator, patch validator, and safe patch application engine."""

import difflib
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Tuple


class DiffEngine:
    """Engine for generating, previewing, and safely applying unified git diffs."""

    @staticmethod
    def generate_unified_diff(
        target_filename: str,
        original_content: str,
        proposed_content: str,
    ) -> str:
        """Produce standard git-compatible unified diff."""
        orig_lines = original_content.splitlines(keepends=True)
        prop_lines = proposed_content.splitlines(keepends=True)

        # Ensure newline at EOF for clean diff formatting
        if orig_lines and not orig_lines[-1].endswith("\n"):
            orig_lines[-1] += "\n"
        if prop_lines and not prop_lines[-1].endswith("\n"):
            prop_lines[-1] += "\n"

        diff_lines = list(
            difflib.unified_diff(
                orig_lines,
                prop_lines,
                fromfile=f"a/{target_filename}",
                tofile=f"b/{target_filename}",
                lineterm="\n",
            )
        )
        return "".join(diff_lines)

    @staticmethod
    def analyze_diff(diff_content: str) -> Dict[str, int]:
        """Extract statistical counts of additions, deletions, and hunks from a diff."""
        added = 0
        removed = 0
        hunks = 0
        for line in diff_content.splitlines():
            if line.startswith("@@"):
                hunks += 1
            elif line.startswith("+") and not line.startswith("+++"):
                added += 1
            elif line.startswith("-") and not line.startswith("---"):
                removed += 1

        return {
            "additions": added,
            "deletions": removed,
            "hunks": hunks,
        }

    @staticmethod
    def dry_run_patch(file_path: Path, expected_original: str) -> Tuple[bool, Optional[str]]:
        """Verify target file exists and content matches expected original state."""
        if not file_path.exists():
            return False, f"Target file '{file_path}' does not exist."

        current_content = file_path.read_text(encoding="utf-8", errors="replace")
        if current_content != expected_original:
            return False, "Target file has drifted: current file content does not match proposal baseline."

        return True, None

    @classmethod
    def apply_patch_safely(
        cls,
        file_path: Path,
        expected_original: str,
        proposed_content: str,
        create_backup: bool = True,
    ) -> Tuple[bool, Optional[str], Optional[Path]]:
        """Apply proposed content with validation and atomic backup for rollback."""
        ok, err = cls.dry_run_patch(file_path, expected_original)
        if not ok:
            return False, err, None

        backup_path: Optional[Path] = None
        if create_backup:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            backup_path = file_path.with_name(f"{file_path.name}.bak_{timestamp}")
            shutil.copy2(file_path, backup_path)

        # Atomic write via temporary file
        temp_file = file_path.with_name(f"{file_path.name}.tmp_{datetime.now(timezone.utc).timestamp()}")
        try:
            temp_file.write_text(proposed_content, encoding="utf-8")
            temp_file.replace(file_path)
            return True, None, backup_path
        except Exception as write_err:
            if temp_file.exists():
                temp_file.unlink()
            if backup_path and backup_path.exists():
                shutil.copy2(backup_path, file_path)
            return False, f"Failed to apply patch: {write_err}", backup_path
