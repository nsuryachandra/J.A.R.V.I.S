"""Approval service managing canonical argument binding, lifecycle, and atomic single-use consumption."""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
from uuid import UUID
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import get_settings
from app.core.exceptions import (
    ApprovalExpiredError,
    EntityNotFoundError,
    InvalidApprovalError,
    PermissionDeniedError,
    ReplayDetectedError,
)
from app.models.approval import ApprovalRequest
from app.models.base import ensure_utc


def canonicalize_arguments(arguments: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
    """Sort dictionary keys recursively and compute canonical SHA-256 argument hash."""
    canonical_json_str = json.dumps(arguments, sort_keys=True, separators=(",", ":"))
    arguments_hash = hashlib.sha256(canonical_json_str.encode("utf-8")).hexdigest()
    parsed_canonical = json.loads(canonical_json_str)
    return parsed_canonical, arguments_hash


class ApprovalService:
    """Manages creation, decision recording, and atomic consumption of approvals."""

    @classmethod
    async def create_request(
        cls,
        session: AsyncSession,
        user_id: UUID,
        tool_name: str,
        tool_version: str,
        arguments: Dict[str, Any],
        target_resource: str,
        risk_class: str = "CONSEQUENTIAL",
        session_id: Optional[UUID] = None,
        created_by_agent_run: Optional[str] = None,
        expire_seconds: Optional[int] = None,
    ) -> ApprovalRequest:
        """Create a pending, cryptographically bound approval request."""
        settings = get_settings()
        lifespan = expire_seconds or settings.approval_expire_seconds
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=lifespan)

        normalized_args, args_hash = canonicalize_arguments(arguments)

        uid = UUID(str(user_id)) if not isinstance(user_id, UUID) else user_id
        sid = UUID(str(session_id)) if session_id and not isinstance(session_id, UUID) else session_id

        approval = ApprovalRequest(
            user_id=uid,
            session_id=sid,
            tool_name=tool_name,
            tool_version=tool_version,
            normalized_arguments=normalized_args,
            arguments_hash=args_hash,
            target_resource=target_resource,
            risk_class=risk_class,
            status="PENDING",
            requested_at=now,
            expires_at=expires_at,
            created_by_agent_run=created_by_agent_run,
        )
        session.add(approval)
        await session.flush()
        return approval

    @classmethod
    async def approve_request(
        cls,
        session: AsyncSession,
        approval_id: UUID,
        user_id: UUID,
        approval_method: str = "UI_CONFIRMATION",
    ) -> ApprovalRequest:
        """Grant user approval for a pending request."""
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        result = await session.execute(stmt)
        approval = result.scalar_one_or_none()

        if approval is None:
            raise EntityNotFoundError("ApprovalRequest", approval_id)

        # Enforce user boundary
        if approval.user_id != user_id:
            raise PermissionDeniedError("Not authorized to approve this request")

        now = datetime.now(timezone.utc)
        if now >= ensure_utc(approval.expires_at):
            approval.status = "EXPIRED"
            await session.flush()
            raise ApprovalExpiredError("Cannot approve: request has expired")

        if approval.status != "PENDING":
            raise InvalidApprovalError(f"Cannot approve request with status '{approval.status}'")

        approval.status = "GRANTED"
        approval.approved_at = now
        approval.approval_method = approval_method
        await session.flush()
        return approval

    @classmethod
    async def deny_request(
        cls,
        session: AsyncSession,
        approval_id: UUID,
        user_id: UUID,
    ) -> ApprovalRequest:
        """Deny a proposed action."""
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        result = await session.execute(stmt)
        approval = result.scalar_one_or_none()

        if approval is None:
            raise EntityNotFoundError("ApprovalRequest", approval_id)

        if approval.user_id != user_id:
            raise PermissionDeniedError("Not authorized to deny this request")

        now = datetime.now(timezone.utc)
        approval.status = "DENIED"
        approval.denied_at = now
        await session.flush()
        return approval

    @classmethod
    async def revoke_approval(
        cls,
        session: AsyncSession,
        approval_id: UUID,
        user_id: UUID,
    ) -> ApprovalRequest:
        """Revoke a previously granted approval before consumption."""
        stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        result = await session.execute(stmt)
        approval = result.scalar_one_or_none()

        if approval is None:
            raise EntityNotFoundError("ApprovalRequest", approval_id)

        if approval.user_id != user_id:
            raise PermissionDeniedError("Not authorized to revoke this request")

        if approval.status == "CONSUMED":
            raise InvalidApprovalError("Cannot revoke an approval that has already been consumed")

        now = datetime.now(timezone.utc)
        approval.status = "REVOKED"
        approval.revoked_at = now
        await session.flush()
        return approval

    @classmethod
    async def consume_atomically(
        cls,
        session: AsyncSession,
        approval_id: UUID,
        user_id: UUID,
        expected_tool_name: str,
        expected_arguments_hash: str,
    ) -> bool:
        """Atomically transition status to CONSUMED in a single SQL operation to eliminate race conditions."""
        now = datetime.now(timezone.utc)

        stmt = (
            update(ApprovalRequest)
            .where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.user_id == user_id,
                ApprovalRequest.tool_name == expected_tool_name,
                ApprovalRequest.arguments_hash == expected_arguments_hash,
                ApprovalRequest.status == "GRANTED",
                ApprovalRequest.expires_at > now,
            )
            .values(status="CONSUMED", consumed_at=now)
            .returning(ApprovalRequest.id)
            .execution_options(synchronize_session="fetch")
        )

        result = await session.execute(stmt)
        consumed_id = result.scalar_one_or_none()

        if consumed_id is not None:
            await session.flush()
            return True

        # Atomic update failed: Diagnose exact reason for failure
        stmt_diag = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
        res_diag = await session.execute(stmt_diag)
        req = res_diag.scalar_one_or_none()

        if req is None:
            raise EntityNotFoundError("ApprovalRequest", approval_id)

        if req.user_id != user_id:
            raise PermissionDeniedError("Not authorized to consume this approval")

        if req.status == "CONSUMED":
            raise ReplayDetectedError("Replay detected: approval has already been consumed")

        if now >= ensure_utc(req.expires_at):
            req.status = "EXPIRED"
            await session.flush()
            raise ApprovalExpiredError("Approval has expired")

        if req.tool_name != expected_tool_name or req.arguments_hash != expected_arguments_hash:
            raise InvalidApprovalError(
                "Approval argument mismatch: proposed action parameters do not match approved parameters"
            )

        if req.status != "GRANTED":
            raise InvalidApprovalError(f"Approval is in status '{req.status}', expected 'GRANTED'")

        return False
