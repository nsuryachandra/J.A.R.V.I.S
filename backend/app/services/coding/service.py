"""Domain service for Coding Agent sessions, change proposals, approval integration, and sandboxed tests."""

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.approval import ApprovalRequest
from app.models.coding import CodeChangeProposal, CodeExecutionRun, CodingSession
from app.models.user import User
from app.services.approval_service import ApprovalService
from app.services.audit_service import AuditService
from app.services.coding.coding_agent import CodingAgent
from app.services.coding.diff_engine import DiffEngine
from app.services.coding.inspector import CodeInspector
from app.services.coding.schemas import (
    ApplyChangeResponse,
    CodeChangeProposalResponse,
    CodingSessionSummary,
    CreateCodingSessionRequest,
    InspectCodeRequest,
    InspectCodeResponse,
    ProposeChangeRequest,
    RunTestsRequest,
    TestExecutionResponse,
)
from app.services.policy_broker import BrokerDecision, PolicyBroker


class CodingService:
    """Service orchestrating code inspection, refactoring proposals, and sandboxed test execution."""

    def __init__(self, broker: Optional[PolicyBroker] = None):
        self._agent = CodingAgent()
        self._broker = broker or PolicyBroker()

    async def create_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: CreateCodingSessionRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> CodingSessionSummary:
        """Create a new coding workspace session."""
        resolved_path = str(Path(request.workspace_path).resolve())

        session_rec = CodingSession(
            user_id=user_id,
            workspace_path=resolved_path,
            title=request.title,
            status="ACTIVE",
        )
        db.add(session_rec)
        await db.commit()
        await db.refresh(session_rec)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="code.session_create",
            resource_scope=f"coding_session:{session_rec.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={"title": session_rec.title, "workspace_path": session_rec.workspace_path},
        )
        await db.commit()

        return CodingSessionSummary(
            id=session_rec.id,
            user_id=session_rec.user_id,
            workspace_path=session_rec.workspace_path,
            title=session_rec.title,
            status=session_rec.status,
            proposals_count=0,
            created_at=session_rec.created_at.isoformat(),
        )

    async def list_user_sessions(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
    ) -> List[CodingSessionSummary]:
        """List authenticated user's coding sessions."""
        stmt = (
            select(CodingSession)
            .where(CodingSession.user_id == user_id)
            .options(selectinload(CodingSession.proposals))
            .order_by(desc(CodingSession.created_at))
        )
        result = await db.execute(stmt)
        sessions = result.scalars().all()

        return [
            CodingSessionSummary(
                id=s.id,
                user_id=s.user_id,
                workspace_path=s.workspace_path,
                title=s.title,
                status=s.status,
                proposals_count=len(s.proposals),
                created_at=s.created_at.isoformat() if s.created_at else "",
            )
            for s in sessions
        ]

    async def get_session(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: uuid.UUID,
    ) -> Optional[CodingSession]:
        """Fetch coding session ensuring tenant isolation."""
        stmt = (
            select(CodingSession)
            .where(CodingSession.id == session_id, CodingSession.user_id == user_id)
            .options(selectinload(CodingSession.proposals), selectinload(CodingSession.execution_runs))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def inspect_code(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: InspectCodeRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> InspectCodeResponse:
        """Inspect workspace code files and AST symbols safely."""
        target_dir = request.workspace_path or str(Path.cwd().resolve())

        inspection = self._agent.inspect_target(
            workspace_path=target_dir,
            relative_file_path=request.relative_file_path,
            max_depth=request.max_depth,
            include_symbols=request.include_symbols,
        )

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="code.inspect",
            resource_scope=f"workspace:{target_dir}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "workspace": target_dir,
                "file": request.relative_file_path,
                "total_files": inspection.total_files,
            },
        )
        await db.commit()

        return inspection

    async def propose_change(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: ProposeChangeRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> CodeChangeProposalResponse:
        """Generate unified diff and persist proposal under review state."""
        session_rec = await self.get_session(db, user_id, request.session_id)
        if not session_rec:
            raise EntityNotFoundError("CodingSession", request.session_id)

        orig_content, diff, stats = self._agent.prepare_change_proposal(
            workspace_path=session_rec.workspace_path,
            relative_file_path=request.target_file,
            proposed_content=request.proposed_content,
        )

        proposal = CodeChangeProposal(
            session_id=session_rec.id,
            user_id=user_id,
            title=request.title,
            description=request.description,
            target_file=request.target_file,
            diff_content=diff,
            original_content=orig_content,
            proposed_content=request.proposed_content,
            status="PENDING_APPROVAL",
        )
        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)

        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="code.propose_change",
            resource_scope=f"code_proposal:{proposal.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            details={
                "target_file": proposal.target_file,
                "additions": stats["additions"],
                "deletions": stats["deletions"],
            },
        )
        await db.commit()

        return CodeChangeProposalResponse(
            id=proposal.id,
            session_id=proposal.session_id,
            user_id=proposal.user_id,
            title=proposal.title,
            description=proposal.description,
            target_file=proposal.target_file,
            diff_content=proposal.diff_content,
            status=proposal.status,
            approval_id=proposal.approval_id,
            applied_at=proposal.applied_at.isoformat() if proposal.applied_at else None,
            created_at=proposal.created_at.isoformat() if proposal.created_at else "",
        )

    async def list_proposals(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None,
    ) -> List[CodeChangeProposalResponse]:
        """List proposals filtered by tenant isolation."""
        stmt = select(CodeChangeProposal).where(CodeChangeProposal.user_id == user_id)
        if session_id:
            stmt = stmt.where(CodeChangeProposal.session_id == session_id)
        stmt = stmt.order_by(desc(CodeChangeProposal.created_at))

        result = await db.execute(stmt)
        proposals = result.scalars().all()

        return [
            CodeChangeProposalResponse(
                id=p.id,
                session_id=p.session_id,
                user_id=p.user_id,
                title=p.title,
                description=p.description,
                target_file=p.target_file,
                diff_content=p.diff_content,
                status=p.status,
                approval_id=p.approval_id,
                applied_at=p.applied_at.isoformat() if p.applied_at else None,
                created_at=p.created_at.isoformat() if p.created_at else "",
            )
            for p in proposals
        ]

    async def get_proposal(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        proposal_id: uuid.UUID,
    ) -> Optional[CodeChangeProposal]:
        """Fetch single proposal ensuring user isolation."""
        stmt = (
            select(CodeChangeProposal)
            .where(CodeChangeProposal.id == proposal_id, CodeChangeProposal.user_id == user_id)
            .options(selectinload(CodeChangeProposal.session))
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def apply_change(
        self,
        db: AsyncSession,
        user: User,
        proposal_id: uuid.UUID,
        approval_id: Optional[uuid.UUID] = None,
        dry_run: bool = False,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> ApplyChangeResponse:
        """Apply approved proposal to target file with Policy Broker consequential enforcement."""
        proposal = await self.get_proposal(db, user.id, proposal_id)
        if not proposal:
            raise EntityNotFoundError("CodeChangeProposal", proposal_id)

        if proposal.status == "APPLIED":
            return ApplyChangeResponse(
                proposal_id=proposal.id,
                status=proposal.status,
                applied=False,
                message="Proposal has already been applied.",
            )

        workspace_path = proposal.session.workspace_path
        target_path = CodeInspector.validate_safe_path(workspace_path, proposal.target_file)

        # Dry-run execution
        if dry_run:
            ok, err = DiffEngine.dry_run_patch(target_path, proposal.original_content)
            return ApplyChangeResponse(
                proposal_id=proposal.id,
                status=proposal.status,
                applied=False,
                message="Dry run succeeded: patch can be cleanly applied." if ok else f"Dry run failed: {err}",
            )

        # Policy Broker consequential approval check
        eval_result = await self._broker.evaluate_action(
            session=db,
            actor=user,
            tool_name="code.apply_change",
            arguments={"proposal_id": str(proposal.id), "target_file": proposal.target_file},
            target_resource=f"file:{target_path}",
            approval_id=approval_id,
            session_id=session_id_auth,
        )

        if eval_result.decision != BrokerDecision.ALLOW:
            if eval_result.decision == BrokerDecision.REQUIRE_APPROVAL:
                # Store link to approval request on proposal
                if eval_result.approval_request:
                    proposal.approval_id = eval_result.approval_request.id
                    await db.commit()
                raise PermissionDeniedError(
                    f"Approval required to apply consequential file modification. Approval request ID: {proposal.approval_id}"
                )
            raise PermissionDeniedError(f"Action denied by Policy Broker: {eval_result.reason}")

        # Apply patch atomically
        success, error, backup_path = DiffEngine.apply_patch_safely(
            file_path=target_path,
            expected_original=proposal.original_content,
            proposed_content=proposal.proposed_content,
            create_backup=True,
        )

        if not success:
            proposal.status = "FAILED"
            await db.commit()
            return ApplyChangeResponse(
                proposal_id=proposal.id,
                status="FAILED",
                applied=False,
                message=error or "Failed to apply patch.",
            )

        # Mark applied
        proposal.status = "APPLIED"
        proposal.applied_at = datetime.now(timezone.utc)
        await db.commit()

        # Audit event
        await AuditService.record_event(
            session=db,
            user_id=user.id,
            session_id=session_id_auth,
            action_type="code.apply_change",
            resource_scope=f"code_proposal:{proposal.id}",
            decision="ALLOW",
            result_status="SUCCESS",
            approval_id=approval_id,
            details={
                "target_file": proposal.target_file,
                "backup_file": str(backup_path) if backup_path else None,
            },
        )
        await db.commit()

        return ApplyChangeResponse(
            proposal_id=proposal.id,
            status="APPLIED",
            applied=True,
            backup_file=str(backup_path) if backup_path else None,
            message=f"Successfully applied changes to '{proposal.target_file}'.",
        )

    async def run_tests(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        request: RunTestsRequest,
        session_id_auth: Optional[uuid.UUID] = None,
    ) -> TestExecutionResponse:
        """Run sandboxed pytest in the target workspace and record test run."""
        workspace = request.workspace_path
        session_rec = None

        if request.session_id:
            session_rec = await self.get_session(db, user_id, request.session_id)
            if session_rec:
                workspace = session_rec.workspace_path

        if not workspace:
            workspace = str(Path.cwd().resolve())

        # Execute in sandbox runner
        run_res = await self._agent.execute_tests(
            workspace_path=workspace,
            test_target=request.test_target,
            timeout_seconds=request.timeout_seconds,
        )

        # Persist execution run if linked to session
        if session_rec:
            run_rec = CodeExecutionRun(
                session_id=session_rec.id,
                user_id=user_id,
                command=run_res.command,
                sandbox_dir=workspace,
                exit_code=run_res.exit_code,
                stdout=run_res.stdout,
                stderr=run_res.stderr,
                duration_ms=run_res.duration_ms,
                passed=run_res.passed,
            )
            db.add(run_rec)
            await db.commit()

        # Audit
        await AuditService.record_event(
            session=db,
            user_id=user_id,
            session_id=session_id_auth,
            action_type="code.run_tests",
            resource_scope=f"workspace:{workspace}",
            decision="ALLOW",
            result_status="SUCCESS" if run_res.passed else "FAILURE",
            details={
                "command": run_res.command,
                "passed": run_res.passed,
                "total_tests": run_res.total_tests,
                "duration_ms": run_res.duration_ms,
            },
        )
        await db.commit()

        run_res.session_id = request.session_id
        return run_res
