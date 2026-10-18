"""Sandboxed execution runner for automated tests and static diagnostics."""

import asyncio
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Optional
from app.services.coding.schemas import TestExecutionResponse


class SandboxRunner:
    """Safely executes allowlisted commands and tests inside bounded directories."""

    # Prohibited commands and tokens
    DANGEROUS_PATTERNS = [
        re.compile(r"rm\s+-rf\s+[/~]", re.IGNORECASE),
        re.compile(r"(curl|wget)\s+.*?\|\s*(bash|sh)", re.IGNORECASE),
        re.compile(r"mkfs", re.IGNORECASE),
        re.compile(r":\(\)\{\s*:\|:&\s*\};:", re.IGNORECASE),
        re.compile(r"chmod\s+777\s+/", re.IGNORECASE),
        re.compile(r">\s*/dev/sd[a-z]", re.IGNORECASE),
    ]

    ALLOWED_PROGRAMS = {
        "pytest",
        "python",
        "python.exe",
        "python3",
        "py_compile",
        "unittest",
        "ruff",
        "flake8",
    }

    MAX_OUTPUT_BYTES = 65536  # 64 KB stdout/stderr cap

    @classmethod
    def validate_command_safety(cls, cmd_args: List[str]) -> None:
        """Reject unallowlisted programs or dangerous shell payloads."""
        if not cmd_args:
            raise ValueError("Command arguments cannot be empty.")

        program = Path(cmd_args[0]).name.lower()
        if program not in cls.ALLOWED_PROGRAMS and not program.endswith("python.exe"):
            raise ValueError(f"Program '{cmd_args[0]}' is not in the sandbox allowlist.")

        joined = " ".join(cmd_args)
        for pattern in cls.DANGEROUS_PATTERNS:
            if pattern.search(joined):
                raise ValueError("Command contains blocked destructive pattern.")

    @classmethod
    async def run_sandboxed_test(
        cls,
        cwd: str,
        test_target: Optional[str] = None,
        timeout_seconds: int = 15,
        session_id: Optional[str] = None,
    ) -> TestExecutionResponse:
        """Run pytest in target directory with strict timeouts and output capture."""
        working_dir = Path(cwd).resolve()
        if not working_dir.exists():
            raise FileNotFoundError(f"Working directory does not exist: '{working_dir}'")

        # Use current Python executable to invoke pytest module
        cmd = [sys.executable, "-m", "pytest"]
        if test_target:
            # Enforce that test_target stays relative to working_dir
            target_path = Path(test_target)
            if target_path.is_absolute():
                target_path = target_path.relative_to(working_dir)
            cmd.append(str(target_path))
        else:
            cmd.extend(["-v", "--maxfail=10"])

        cls.validate_command_safety(cmd)

        start_time = time.monotonic()
        stdout_text = ""
        stderr_text = ""
        exit_code = -1
        passed = False

        try:
            # Run without shell=True to eliminate command injection vulnerabilities
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(working_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=dict(os.environ),
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=float(timeout_seconds),
            )

            exit_code = proc.returncode if proc.returncode is not None else -1
            passed = (exit_code == 0)

            stdout_text = stdout_bytes[:cls.MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
            stderr_text = stderr_bytes[:cls.MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")

        except asyncio.TimeoutError:
            exit_code = 124
            passed = False
            stderr_text = f"Execution timed out after {timeout_seconds} seconds."
            try:
                proc.kill()
            except Exception:
                pass
        except Exception as err:
            exit_code = 1
            passed = False
            stderr_text = f"Sandbox execution error: {err}"

        duration_ms = int((time.monotonic() - start_time) * 1000)

        # Parse test metrics from stdout
        passed_count, failed_count, total_tests = cls.parse_pytest_output(stdout_text)

        return TestExecutionResponse(
            command=" ".join(cmd),
            exit_code=exit_code,
            passed=passed,
            total_tests=total_tests,
            passed_count=passed_count,
            failed_count=failed_count,
            duration_ms=duration_ms,
            stdout=stdout_text,
            stderr=stderr_text,
        )

    @staticmethod
    def parse_pytest_output(stdout: str) -> tuple[int, int, int]:
        """Extract test count statistics from standard pytest output lines."""
        passed = 0
        failed = 0

        # Pattern: "X passed, Y failed in Zs" or "X passed in Zs"
        pass_match = re.search(r"(\d+)\s+passed", stdout)
        if pass_match:
            passed = int(pass_match.group(1))

        fail_match = re.search(r"(\d+)\s+failed", stdout)
        if fail_match:
            failed = int(fail_match.group(1))

        error_match = re.search(r"(\d+)\s+error", stdout)
        if error_match:
            failed += int(error_match.group(1))

        total = passed + failed
        return passed, failed, total
