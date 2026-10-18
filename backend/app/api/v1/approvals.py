"""Approval management API endpoints for human-in-the-loop authorization."""

from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_current_user
from app.core.database import get_db_session
from app.core.exceptions import EntityNotFoundError, PermissionDeniedError
from app.models.approval import ApprovalRequest
from app.models.user import User
from app.schemas.approval import ApprovalDecisionRequest, ApprovalResponse
from app.services.approval_service import ApprovalService

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.get("", response_model=List[ApprovalResponse])
async def list_approvals(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> List[ApprovalResponse]:
    """List all approval requests belonging to the current user."""
    stmt = (
        select(ApprovalRequest)
        .where(ApprovalRequest.user_id == current_user.id)
        .order_by(ApprovalRequest.requested_at.desc())
    )
    res = await db.execute(stmt)
    approvals = res.scalars().all()

    return [
        ApprovalResponse(
            id=a.id,
            tool_name=a.tool_name,
            tool_version=a.tool_version,
            normalized_arguments=a.normalized_arguments,
            arguments_hash=a.arguments_hash,
            target_resource=a.target_resource,
            risk_class=a.risk_class,
            status=a.status,
            requested_at=a.requested_at,
            expires_at=a.expires_at,
            approved_at=a.approved_at,
            consumed_at=a.consumed_at,
            denied_at=a.denied_at,
            revoked_at=a.revoked_at,
            approval_method=a.approval_method,
        )
        for a in approvals
    ]


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Retrieve details of a specific approval request."""
    stmt = select(ApprovalRequest).where(ApprovalRequest.id == approval_id)
    res = await db.execute(stmt)
    approval = res.scalar_one_or_none()

    if approval is None:
        raise EntityNotFoundError("ApprovalRequest", approval_id)

    if approval.user_id != current_user.id:
        raise PermissionDeniedError("Not authorized to view this approval")

    return ApprovalResponse(
        id=approval.id,
        tool_name=approval.tool_name,
        tool_version=approval.tool_version,
        normalized_arguments=approval.normalized_arguments,
        arguments_hash=approval.arguments_hash,
        target_resource=approval.target_resource,
        risk_class=approval.risk_class,
        status=approval.status,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        approved_at=approval.approved_at,
        consumed_at=approval.consumed_at,
        denied_at=approval.denied_at,
        revoked_at=approval.revoked_at,
        approval_method=approval.approval_method,
    )


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: UUID,
    payload: ApprovalDecisionRequest = ApprovalDecisionRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Approve a proposed consequential action."""
    approval = await ApprovalService.approve_request(
        session=db,
        approval_id=approval_id,
        user_id=current_user.id,
        approval_method=payload.approval_method,
    )
    return ApprovalResponse(
        id=approval.id,
        tool_name=approval.tool_name,
        tool_version=approval.tool_version,
        normalized_arguments=approval.normalized_arguments,
        arguments_hash=approval.arguments_hash,
        target_resource=approval.target_resource,
        risk_class=approval.risk_class,
        status=approval.status,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        approved_at=approval.approved_at,
        consumed_at=approval.consumed_at,
        denied_at=approval.denied_at,
        revoked_at=approval.revoked_at,
        approval_method=approval.approval_method,
    )


@router.post("/{approval_id}/deny", response_model=ApprovalResponse)
async def deny(
    approval_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Deny a proposed action."""
    approval = await ApprovalService.deny_request(
        session=db,
        approval_id=approval_id,
        user_id=current_user.id,
    )
    return ApprovalResponse(
        id=approval.id,
        tool_name=approval.tool_name,
        tool_version=approval.tool_version,
        normalized_arguments=approval.normalized_arguments,
        arguments_hash=approval.arguments_hash,
        target_resource=approval.target_resource,
        risk_class=approval.risk_class,
        status=approval.status,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        approved_at=approval.approved_at,
        consumed_at=approval.consumed_at,
        denied_at=approval.denied_at,
        revoked_at=approval.revoked_at,
        approval_method=approval.approval_method,
    )


@router.post("/{approval_id}/revoke", response_model=ApprovalResponse)
async def revoke(
    approval_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> ApprovalResponse:
    """Revoke a previously granted approval before consumption."""
    approval = await ApprovalService.revoke_approval(
        session=db,
        approval_id=approval_id,
        user_id=current_user.id,
    )
    return ApprovalResponse(
        id=approval.id,
        tool_name=approval.tool_name,
        tool_version=approval.tool_version,
        normalized_arguments=approval.normalized_arguments,
        arguments_hash=approval.arguments_hash,
        target_resource=approval.target_resource,
        risk_class=approval.risk_class,
        status=approval.status,
        requested_at=approval.requested_at,
        expires_at=approval.expires_at,
        approved_at=approval.approved_at,
        consumed_at=approval.consumed_at,
        denied_at=approval.denied_at,
        revoked_at=approval.revoked_at,
        approval_method=approval.approval_method,
    )
