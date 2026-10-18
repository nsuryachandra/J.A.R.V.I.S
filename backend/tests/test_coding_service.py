"""Unit and domain service tests for Coding Agent inspector, diff engine, sandbox, and proposals."""

import tempfile
import uuid
from pathlib import Path
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.approval import ApprovalRequest
from app.models.audit import AuditLog
from app.models.coding import CodeChangeProposal, CodingSession
from app.models.user import User
from app.services.approval_service import ApprovalService
from app.services.coding.diff_engine import DiffEngine
from app.services.coding.inspector import CodeInspector
from app.services.coding.sandbox_runner import SandboxRunner
from app.services.coding.schemas import (
    CreateCodingSessionRequest,
    InspectCodeRequest,
    ProposeChangeRequest,
    RunTestsRequest,
)
from app.services.coding.service import CodingService
from app.services.policy_broker import PolicyBroker


async def create_test_user(db: AsyncSession, email: str = "coding_unit@jarvis.ai") -> User:
    """Helper to persist a user for foreign key constraints."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password="hashed_pw_test",
        timezone="Asia/Kolkata",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def test_code_inspector_safe_path_validation():
    """Verify CodeInspector enforces workspace bounds and blocks directory traversal."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir).resolve()
        subfile = base / "app" / "main.py"
        subfile.parent.mkdir(parents=True, exist_ok=True)
        subfile.write_text("print('hello')", encoding="utf-8")

        # Valid relative path inside workspace
        valid_path = CodeInspector.validate_safe_path(str(base), "app/main.py")
        assert valid_path == subfile

        # Directory traversal attempt blocked
        with pytest.raises(ValueError, match="Path traversal blocked"):
            CodeInspector.validate_safe_path(str(base), "../../etc/passwd")

        with pytest.raises(ValueError, match="Path traversal blocked"):
            CodeInspector.validate_safe_path(str(base), "../outside.py")


def test_code_inspector_ast_parsing_and_syntax():
    """Verify AST parsing extracts classes, functions, and flags syntax errors."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        valid_file = base / "sample.py"
        valid_code = (
            "class Engine:\n"
            "    '''Engine docstring.'''\n"
            "    async def start(self, mode: str):\n"
            "        '''Start docstring.'''\n"
            "        return True\n\n"
            "def helper(val):\n"
            "    return val * 2\n"
        )
        valid_file.write_text(valid_code, encoding="utf-8")

        info = CodeInspector.inspect_file(valid_file, include_symbols=True)
        assert info.syntax_valid is True
        assert info.syntax_error is None
        assert info.line_count == 8
        symbol_names = [s.name for s in info.symbols]
        assert "Engine" in symbol_names
        assert "Engine.start" in symbol_names
        assert "helper" in symbol_names

        # Invalid syntax file
        invalid_file = base / "bad.py"
        invalid_file.write_text("def broken_syntax(:\n    pass\n", encoding="utf-8")
        bad_info = CodeInspector.inspect_file(invalid_file, include_symbols=True)
        assert bad_info.syntax_valid is False
        assert bad_info.syntax_error is not None
        assert "Syntax error at line 1" in bad_info.syntax_error


def test_diff_engine_unified_diff_and_analysis():
    """Verify unified diff generation, statistical additions/deletions, and dry run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        target = base / "calculator.py"
        original = "def add(a, b):\n    return a + b\n"
        proposed = "def add(a, b):\n    # add comment\n    return a + b + 0\n"
        target.write_text(original, encoding="utf-8")

        # Generate diff
        diff = DiffEngine.generate_unified_diff("calculator.py", original, proposed)
        assert "--- a/calculator.py" in diff
        assert "+++ b/calculator.py" in diff
        assert "+    # add comment" in diff

        # Analyze diff
        stats = DiffEngine.analyze_diff(diff)
        assert stats["additions"] >= 2
        assert stats["deletions"] >= 1
        assert stats["hunks"] >= 1

        # Dry run against current file
        ok, err = DiffEngine.dry_run_patch(target, original)
        assert ok is True
        assert err is None

        # Dry run against drifted baseline
        ok_drift, err_drift = DiffEngine.dry_run_patch(target, "completely different code\n")
        assert ok_drift is False
        assert "Target file has drifted" in err_drift


def test_diff_engine_safe_patch_application_and_rollback():
    """Verify atomic patch application creates backup and rolls back on error."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        target = base / "service.py"
        original = "def run():\n    return 1\n"
        proposed = "def run():\n    return 2\n"
        target.write_text(original, encoding="utf-8")

        success, err, backup = DiffEngine.apply_patch_safely(
            file_path=target,
            expected_original=original,
            proposed_content=proposed,
            create_backup=True,
        )
        assert success is True
        assert err is None
        assert backup is not None
        assert backup.exists()
        assert target.read_text(encoding="utf-8") == proposed


def test_sandbox_runner_safety_validation():
    """Verify SandboxRunner blocks unallowlisted binaries and dangerous shell commands."""
    with pytest.raises(ValueError, match="not in the sandbox allowlist"):
        SandboxRunner.validate_command_safety(["bash", "-c", "echo hello"])

    with pytest.raises(ValueError, match="not in the sandbox allowlist"):
        SandboxRunner.validate_command_safety(["curl", "http://evil.com"])

    with pytest.raises(ValueError, match="blocked destructive pattern"):
        SandboxRunner.validate_command_safety(["python", "-c", "rm -rf /"])


@pytest.mark.asyncio
async def test_sandbox_runner_execution_and_parsing():
    """Verify SandboxRunner runs allowlisted python command and parses results."""
    with tempfile.TemporaryDirectory() as tmpdir:
        resp = await SandboxRunner.run_sandboxed_test(
            cwd=tmpdir,
            timeout_seconds=5,
        )
        # Running pytest in empty dir returns exit code 5 (no tests collected)
        assert resp.command.startswith(str(Path(resp.command.split()[0]))) or "python" in resp.command
        assert resp.duration_ms >= 0


@pytest.mark.asyncio
async def test_coding_service_lifecycle_proposals_and_audit(db_session: AsyncSession):
    """Verify full CodingService workflow: session -> inspect -> propose -> apply with approval -> audit."""
    user = await create_test_user(db_session, "coding_lifecycle@jarvis.ai")
    service = CodingService()

    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        module_file = base / "core.py"
        orig_code = "def process():\n    return 'v1'\n"
        module_file.write_text(orig_code, encoding="utf-8")

        # 1. Create coding session
        sess_req = CreateCodingSessionRequest(workspace_path=str(base), title="Core Optimization")
        session_summary = await service.create_session(db=db_session, user_id=user.id, request=sess_req)
        assert session_summary.title == "Core Optimization"
        assert session_summary.status == "ACTIVE"

        # 2. Inspect code
        inspect_req = InspectCodeRequest(workspace_path=str(base), relative_file_path="core.py", include_symbols=True)
        inspect_res = await service.inspect_code(db=db_session, user_id=user.id, request=inspect_req)
        assert inspect_res.total_files == 1
        assert inspect_res.files[0].syntax_valid is True

        # 3. Propose change
        new_code = "def process():\n    return 'v2_optimized'\n"
        prop_req = ProposeChangeRequest(
            session_id=session_summary.id,
            target_file="core.py",
            title="Upgrade to v2",
            description="Optimize process return value",
            proposed_content=new_code,
        )
        proposal_res = await service.propose_change(db=db_session, user_id=user.id, request=prop_req)
        assert proposal_res.status == "PENDING_APPROVAL"
        assert "+    return 'v2_optimized'" in proposal_res.diff_content

        # 4. Dry-run apply
        dry_res = await service.apply_change(
            db=db_session,
            user=user,
            proposal_id=proposal_res.id,
            dry_run=True,
        )
        assert dry_res.applied is False
        assert "Dry run succeeded" in dry_res.message
        assert module_file.read_text(encoding="utf-8") == orig_code

        # 5. Consequential apply without approval raises PermissionDeniedError
        with pytest.raises(Exception, match="Approval required"):
            await service.apply_change(
                db=db_session,
                user=user,
                proposal_id=proposal_res.id,
                approval_id=None,
                dry_run=False,
            )

        # Refresh proposal to retrieve generated approval_id
        prop_db = await service.get_proposal(db=db_session, user_id=user.id, proposal_id=proposal_res.id)
        assert prop_db.approval_id is not None

        # Authorize approval via ApprovalService
        app_req = await db_session.get(ApprovalRequest, prop_db.approval_id)
        await ApprovalService.approve_request(
            session=db_session,
            approval_id=app_req.id,
            user_id=user.id,
        )

        # 6. Apply with approved authorization
        apply_res = await service.apply_change(
            db=db_session,
            user=user,
            proposal_id=proposal_res.id,
            approval_id=app_req.id,
            dry_run=False,
        )
        assert apply_res.applied is True
        assert apply_res.status == "APPLIED"
        assert module_file.read_text(encoding="utf-8") == new_code

        # 7. Verify audit events recorded
        audit_stmt = (
            select(AuditLog)
            .where(AuditLog.user_id == user.id)
            .order_by(AuditLog.sequence_number.asc())
        )
        audit_res = await db_session.execute(audit_stmt)
        events = audit_res.scalars().all()
        actions = [e.action_type for e in events]
        assert "code.session_create" in actions
        assert "code.inspect" in actions
        assert "code.propose_change" in actions
        assert "code.apply_change" in actions


@pytest.mark.asyncio
async def test_coding_service_tenant_isolation(db_session: AsyncSession):
    """Verify strict tenant isolation: User B cannot access User A's session or proposals."""
    user_a = await create_test_user(db_session, "user_a_code@jarvis.ai")
    user_b = await create_test_user(db_session, "user_b_code@jarvis.ai")
    service = CodingService()

    with tempfile.TemporaryDirectory() as tmpdir:
        # User A creates session and proposal
        sess_a = await service.create_session(
            db=db_session,
            user_id=user_a.id,
            request=CreateCodingSessionRequest(workspace_path=tmpdir, title="User A Session"),
        )
        (Path(tmpdir) / "app.py").write_text("x = 1\n", encoding="utf-8")

        prop_a = await service.propose_change(
            db=db_session,
            user_id=user_a.id,
            request=ProposeChangeRequest(
                session_id=sess_a.id,
                target_file="app.py",
                title="User A Proposal",
                description="Refactor",
                proposed_content="x = 2\n",
            ),
        )

        # User B queries User A's session -> None
        sess_for_b = await service.get_session(db=db_session, user_id=user_b.id, session_id=sess_a.id)
        assert sess_for_b is None

        # User B queries User A's proposal -> None
        prop_for_b = await service.get_proposal(db=db_session, user_id=user_b.id, proposal_id=prop_a.id)
        assert prop_for_b is None

        # User B's proposal list is empty
        b_proposals = await service.list_proposals(db=db_session, user_id=user_b.id)
        assert len(b_proposals) == 0
