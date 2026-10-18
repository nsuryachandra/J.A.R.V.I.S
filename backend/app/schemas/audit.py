"""Audit log serialization schemas."""

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID
from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """Immutable audit record representation."""
    id: UUID
    sequence_number: int
    user_id: Optional[UUID]
    tool_name: Optional[str]
    risk_class: Optional[str]
    action_type: str
    decision: str
    result_status: str
    error_code: Optional[str]
    details: Dict[str, Any]
    correlation_id: Optional[str]
    previous_hash: str
    record_hash: str
    created_at: datetime
