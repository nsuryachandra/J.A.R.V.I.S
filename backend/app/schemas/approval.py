"""Approval schemas for human-in-the-loop consequential action authorization."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel


class ApprovalResponse(BaseModel):
    """Details of an approval request presented to the user."""
    id: UUID
    tool_name: str
    tool_version: str
    normalized_arguments: Dict[str, Any]
    arguments_hash: str
    target_resource: str
    risk_class: str
    status: str
    requested_at: datetime
    expires_at: datetime
    approved_at: Optional[datetime] = None
    consumed_at: Optional[datetime] = None
    denied_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    approval_method: Optional[str] = None


class ApprovalDecisionRequest(BaseModel):
    """Payload for user decision on a pending approval."""
    approval_method: str = "UI_CONFIRMATION"
    notes: Optional[str] = None
